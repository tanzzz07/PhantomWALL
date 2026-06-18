from datetime import datetime, timedelta, timezone
import json

from sqlalchemy import Integer, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Install, TrackerEventRecord, User, BlockedRequest, DomainReputation
from app.schemas.analytics import (
    BlockedScriptRecord,
    DomainCount,
    InstallTraffic,
    StatsResponse,
    TrackerEvent,
    TrackEventIn,
)
from app.services.classifier import TrackerClassifier
from feature_engineering.extractor import FeatureExtractor
from inference.predictor import Predictor
from app.services.explanation_service import ExplanationService


class AnalyticsService:
    """Database-backed analytics queries and writes."""

    def __init__(self, max_recent_events: int = 100) -> None:
        self._max_recent_events = max_recent_events

    async def ingest_event(
        self,
        session: AsyncSession,
        install: Install,
        event: TrackEventIn,
    ) -> tuple[StatsResponse, BlockedRequest]:
        # Resolve domain, timestamp, referrer, and action from telemetry inputs (supporting old and new schemas)
        domain = event.domain or event.tracker_domain or "unknown"
        timestamp = event.timestamp or event.occurred_at or datetime.now(timezone.utc)
        referrer = event.referrer or event.page_origin
        action = event.action or ("blocked" if event.blocked else "observed")
        request_type = event.request_type or "other"

        # Get count of events for this install and domain in the last 5 minutes (request frequency)
        time_limit = datetime.now(timezone.utc) - timedelta(minutes=5)
        count_query = select(func.count(TrackerEventRecord.id)).where(
            TrackerEventRecord.install_id == install.id,
            TrackerEventRecord.tracker_domain == domain,
            TrackerEventRecord.occurred_at >= time_limit
        )
        recent_count = await self._scalar_count(session, count_query)

        # Classify the threat level of the event using legacy fallback rules
        legacy_classification = TrackerClassifier.classify(
            domain=domain,
            url=event.url,
            recent_count=recent_count,
            is_third_party=event.third_party,
        )
        class_map = {
            "fingerprinting": "Fingerprinting",
            "advertising": "Advertising",
            "analytics": "Analytics",
            "tracker": "Suspicious",
            "safe": "Safe"
        }
        legacy_classification_cap = class_map.get(legacy_classification.lower(), "Safe")

        # Save standard TrackerEventRecord for backwards compatibility
        record = TrackerEventRecord(
            install_id=install.id,
            tracker_domain=domain,
            url=event.url,
            page_origin=referrer,
            request_type=request_type,
            source=event.source,
            blocked=event.blocked,
            third_party=event.third_party,
            classification=legacy_classification_cap,
            occurred_at=timestamp,
        )
        install.last_seen_at = datetime.now(timezone.utc)
        session.add(record)

        # --- NEW TELEMETRY PIPELINE ---
        # 1. Feature extraction
        raw_features = FeatureExtractor.extract_features(
            url=event.url,
            request_type=request_type,
            third_party=event.third_party,
            request_frequency=recent_count + 1,
            referrer_domain=referrer or "",
            session_occurrence_count=recent_count + 1
        )

        # 2. Predict using final XGBoost classifier model
        predictor = Predictor()
        prediction_result = None
        if predictor.model_loaded:
            prediction_result = predictor.predict(
                url=event.url,
                request_type=request_type,
                third_party=event.third_party,
                request_frequency=recent_count + 1,
                referrer_domain=referrer or ""
            )

        if prediction_result:
            classification = prediction_result["prediction"]
            confidence = prediction_result["confidence"]
        else:
            classification = legacy_classification_cap
            confidence = 1.0

        # 3. Calculate dynamic risk score (0-100)
        # risk_score = category_weight * confidence * 100
        category_weights = {
            "Safe": 0.1,
            "Analytics": 0.4,
            "Advertising": 0.6,
            "Fingerprinting": 0.85,
            "Suspicious": 1.0
        }
        weight = category_weights.get(classification, 0.1)
        risk_score = int(round(weight * confidence * 100))

        # 4. Generate SHAP explanations
        top_feats, explanation_text = ExplanationService.generate_explanation(
            raw_features=raw_features,
            classification=classification,
            confidence=confidence
        )
        top_features_json = json.dumps(top_feats)

        # 5. Persist BlockedRequest (handles both observed and blocked)
        blocked_record = BlockedRequest(
            user_id=install.user_id,
            timestamp=timestamp,
            full_url=event.url,
            domain=domain,
            request_type=request_type,
            blocked=event.blocked,
            action=action,
            classification=classification,
            confidence=confidence,
            risk_score=risk_score,
            third_party=event.third_party,
            tab_url=event.tab_url,
            referrer=referrer,
            top_features=top_features_json,
            explanation=explanation_text
        )
        session.add(blocked_record)

        # 6. Update Domain Reputation Engine
        rep_query = select(DomainReputation).where(DomainReputation.domain == domain)
        rep_result = await session.execute(rep_query)
        reputation = rep_result.scalar_one_or_none()

        if reputation:
            reputation.times_seen += 1
            if event.blocked:
                reputation.times_blocked += 1
            # Recalculate average risk score
            reputation.average_risk_score = (
                (reputation.average_risk_score * (reputation.times_seen - 1) + risk_score)
                / reputation.times_seen
            )
            reputation.classification = classification
            reputation.last_seen = timestamp
        else:
            reputation = DomainReputation(
                domain=domain,
                times_seen=1,
                times_blocked=1 if event.blocked else 0,
                average_risk_score=float(risk_score),
                classification=classification,
                first_seen=timestamp,
                last_seen=timestamp
            )
            session.add(reputation)

        await session.commit()
        return await self.get_stats(session=session), blocked_record

    async def get_stats(
        self,
        session: AsyncSession,
        user_id: str | None = None,
        install_id: str | None = None,
        recent_limit: int | None = None,
    ) -> StatsResponse:
        base_filters = []
        if install_id:
            base_filters.append(TrackerEventRecord.install_id == install_id)

        q_total = select(func.count(TrackerEventRecord.id)).where(*base_filters)
        if user_id:
            q_total = q_total.join(Install).where(Install.user_id == user_id)
        total_events = await self._scalar_count(session, q_total)

        q_blocked = select(func.count(TrackerEventRecord.id)).where(
            *base_filters,
            TrackerEventRecord.blocked.is_(True),
        )
        if user_id:
            q_blocked = q_blocked.join(Install).where(Install.user_id == user_id)
        blocked_tracker_count = await self._scalar_count(session, q_blocked)

        q_unique = select(func.count(func.distinct(TrackerEventRecord.tracker_domain))).where(
            *base_filters
        )
        if user_id:
            q_unique = q_unique.join(Install).where(Install.user_id == user_id)
        unique_tracker_count = await self._scalar_count(session, q_unique)

        q_install = select(func.count(func.distinct(TrackerEventRecord.install_id))).where(
            *base_filters
        )
        if user_id:
            q_install = q_install.join(Install).where(Install.user_id == user_id)
        unique_install_count = await self._scalar_count(session, q_install)

        top_tracker_domains = await self._top_domains(session, base_filters, user_id)
        request_type_breakdown = await self._request_type_breakdown(session, base_filters, user_id)
        classification_breakdown = await self._classification_breakdown(session, base_filters, user_id)
        installs = await self._install_breakdown(session, user_id, install_id)
        recent_events = await self._recent_events(
            session,
            base_filters,
            recent_limit or self._max_recent_events,
            user_id,
        )

        return StatsResponse(
            blocked_tracker_count=blocked_tracker_count,
            total_events=total_events,
            unique_tracker_count=unique_tracker_count,
            unique_install_count=unique_install_count,
            top_tracker_domains=top_tracker_domains,
            request_type_breakdown=request_type_breakdown,
            classification_breakdown=classification_breakdown,
            installs=installs,
            recent_events=recent_events,
            service_status="online",
            generated_at=datetime.now(timezone.utc),
            selected_install_id=install_id,
        )

    async def list_installs(self, session: AsyncSession, user_id: str | None = None) -> list[InstallTraffic]:
        return await self._install_breakdown(session=session, user_id=user_id, selected_install_id=None)

    async def get_install_by_token(
        self,
        session: AsyncSession,
        token_hash: str,
    ) -> Install | None:
        result = await session.execute(
            select(Install).where(
                Install.token_hash == token_hash,
                Install.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def create_install(
        self,
        session: AsyncSession,
        *,
        display_name: str,
        token_hash: str,
        extension_version: str | None,
        browser_name: str | None,
        notes: str | None,
        user_id: str | None = None,
    ) -> Install:
        install = Install(
            display_name=display_name,
            token_hash=token_hash,
            extension_version=extension_version,
            browser_name=browser_name,
            notes=notes,
            last_seen_at=datetime.now(timezone.utc),
            user_id=user_id,
        )
        session.add(install)
        await session.commit()
        await session.refresh(install)
        return install




    async def _install_breakdown(
        self,
        session: AsyncSession,
        user_id: str | None,
        selected_install_id: str | None,
    ) -> list[InstallTraffic]:
        event_count = func.count(TrackerEventRecord.id)
        blocked_count = func.sum(
            func.cast(TrackerEventRecord.blocked, Integer)
        )
        query = (
            select(
                Install.id,
                Install.display_name,
                func.coalesce(event_count, 0).label("event_count"),
                func.coalesce(blocked_count, 0).label("blocked_count"),
                Install.last_seen_at,
            )
            .select_from(Install)
            .outerjoin(TrackerEventRecord, TrackerEventRecord.install_id == Install.id)
            .group_by(Install.id, Install.display_name, Install.last_seen_at)
            .order_by(func.coalesce(event_count, 0).desc(), Install.created_at.asc())
        )
        if user_id:
            query = query.where(Install.user_id == user_id)
        if selected_install_id:
            query = query.where(Install.id == selected_install_id)


        result = await session.execute(query)
        return [
            InstallTraffic(
                install_id=install_id,
                display_name=display_name,
                event_count=event_count,
                blocked_count=blocked_count,
                last_seen_at=last_seen_at,
            )
            for install_id, display_name, event_count, blocked_count, last_seen_at in result.all()
        ]
    async def _top_domains(
        self,
        session: AsyncSession,
        filters: list,
        user_id: str | None = None,
    ) -> list[DomainCount]:
        query = select(
            TrackerEventRecord.tracker_domain,
            func.count(TrackerEventRecord.id).label("count"),
        ).where(*filters)
        if user_id:
            query = query.join(Install).where(Install.user_id == user_id)
        query = query.group_by(TrackerEventRecord.tracker_domain).order_by(
            func.count(TrackerEventRecord.id).desc()
        ).limit(5)

        result = await session.execute(query)
        return [
            DomainCount(domain=domain, count=count)
            for domain, count in result.all()
        ]

    async def _request_type_breakdown(
        self,
        session: AsyncSession,
        filters: list,
        user_id: str | None = None,
    ) -> list[DomainCount]:
        request_type_expr = func.coalesce(TrackerEventRecord.request_type, "unknown")
        query = select(
            request_type_expr.label("request_type"),
            func.count(TrackerEventRecord.id).label("count"),
        ).where(*filters)
        if user_id:
            query = query.join(Install).where(Install.user_id == user_id)
        query = query.group_by(request_type_expr).order_by(
            func.count(TrackerEventRecord.id).desc()
        ).limit(6)

        result = await session.execute(query)
        return [
            DomainCount(domain=request_type, count=count)
            for request_type, count in result.all()
        ]

    async def _classification_breakdown(
        self,
        session: AsyncSession,
        filters: list,
        user_id: str | None = None,
    ) -> list[DomainCount]:
        classification_expr = func.coalesce(TrackerEventRecord.classification, "Safe")
        query = select(
            classification_expr.label("classification"),
            func.count(TrackerEventRecord.id).label("count"),
        ).where(*filters)
        if user_id:
            query = query.join(Install).where(Install.user_id == user_id)
        query = query.group_by(classification_expr).order_by(
            func.count(TrackerEventRecord.id).desc()
        ).limit(5)

        result = await session.execute(query)
        return [
            DomainCount(domain=classification, count=count)
            for classification, count in result.all()
        ]

    async def _recent_events(
        self,
        session: AsyncSession,
        filters: list,
        limit: int,
        user_id: str | None = None,
    ) -> list[TrackerEvent]:
        query = select(TrackerEventRecord).options(
            selectinload(TrackerEventRecord.install)
        ).where(*filters)
        if user_id:
            query = query.join(Install).where(Install.user_id == user_id)
        query = query.order_by(
            TrackerEventRecord.occurred_at.desc(), TrackerEventRecord.id.desc()
        ).limit(limit)

        result = await session.execute(query)
        records = result.scalars().all()
        return [
            TrackerEvent(
                event_id=record.id,
                install_id=record.install_id,
                install_name=record.install.display_name if record.install else None,
                tracker_domain=record.tracker_domain,
                url=record.url,
                page_origin=record.page_origin,
                request_type=record.request_type,
                source=record.source,
                blocked=record.blocked,
                third_party=record.third_party,
                classification=record.classification or "Safe",
                occurred_at=record.occurred_at,
            )
            for record in records
        ]

    async def get_blocked_scripts(
        self,
        session: AsyncSession,
        user_id: str | None = None,
        install_id: str | None = None,
        limit: int = 50,
    ) -> list[BlockedScriptRecord]:
        query = select(TrackerEventRecord).options(
            selectinload(TrackerEventRecord.install)
        ).where(
            TrackerEventRecord.request_type == "script",
            TrackerEventRecord.blocked.is_(True),
        )
        if install_id:
            query = query.where(TrackerEventRecord.install_id == install_id)
        if user_id:
            query = query.join(Install).where(Install.user_id == user_id)
        query = query.order_by(
            TrackerEventRecord.occurred_at.desc(), TrackerEventRecord.id.desc()
        ).limit(limit)

        result = await session.execute(query)
        records = result.scalars().all()
        return [
            BlockedScriptRecord(
                occurred_at=record.occurred_at,
                page_origin=record.page_origin,
                url=record.url,
                classification=record.classification or "Safe",
                install_name=record.install.display_name if record.install else "Unknown",
            )
            for record in records
        ]

    async def _scalar_count(self, session: AsyncSession, query: Select) -> int:
        result = await session.execute(query)
        return int(result.scalar() or 0)

    async def get_history(
        self,
        session: AsyncSession,
        user_id: str | None = None,
        page: int = 1,
        limit: int = 50,
        classification: str | None = None,
        request_type: str | None = None,
        search: str | None = None
    ) -> dict:
        query = select(BlockedRequest)
        filters = []

        if user_id:
            filters.append(BlockedRequest.user_id == user_id)
        if classification:
            filters.append(BlockedRequest.classification == classification)
        if request_type:
            filters.append(BlockedRequest.request_type == request_type)
        if search:
            filters.append(
                (BlockedRequest.domain.ilike(f"%{search}%")) |
                (BlockedRequest.full_url.ilike(f"%{search}%"))
            )

        if filters:
            query = query.where(*filters)

        count_query = select(func.count(BlockedRequest.id))
        if filters:
            count_query = count_query.where(*filters)
        total = await self._scalar_count(session, count_query)

        query = query.order_by(BlockedRequest.timestamp.desc(), BlockedRequest.id.desc())
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit)

        result = await session.execute(query)
        records = result.scalars().all()

        items = []
        for record in records:
            top_feats = []
            if record.top_features:
                try:
                    top_feats = json.loads(record.top_features)
                except Exception:
                    top_feats = []
            items.append({
                "id": record.id,
                "timestamp": record.timestamp,
                "full_url": record.full_url,
                "domain": record.domain,
                "request_type": record.request_type,
                "blocked": record.blocked,
                "action": record.action,
                "classification": record.classification,
                "confidence": record.confidence,
                "risk_score": record.risk_score,
                "third_party": record.third_party,
                "tab_url": record.tab_url,
                "referrer": record.referrer,
                "top_features": top_feats,
                "explanation": record.explanation
            })

        import math
        pages = math.ceil(total / limit) if limit > 0 else 1

        return {
            "items": items,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": pages
        }

    async def get_history_stats(
        self,
        session: AsyncSession,
        user_id: str | None = None
    ) -> dict:
        filters = []
        if user_id:
            filters.append(BlockedRequest.user_id == user_id)

        total_query = select(func.count(BlockedRequest.id))
        if filters:
            total_query = total_query.where(*filters)
        total_requests = await self._scalar_count(session, total_query)

        blocked_q = select(func.count(BlockedRequest.id)).where(BlockedRequest.blocked.is_(True))
        if filters:
            blocked_q = blocked_q.where(*filters)
        blocked_count = await self._scalar_count(session, blocked_q)

        observed_q = select(func.count(BlockedRequest.id)).where(BlockedRequest.blocked.is_(False))
        if filters:
            observed_q = observed_q.where(*filters)
        observed_count = await self._scalar_count(session, observed_q)

        avg_risk_q = select(func.coalesce(func.avg(BlockedRequest.risk_score), 0.0))
        if filters:
            avg_risk_q = avg_risk_q.where(*filters)
        avg_risk_res = await session.execute(avg_risk_q)
        average_risk_score = float(avg_risk_res.scalar() or 0.0)

        script_query = select(func.count(BlockedRequest.id)).where(
            BlockedRequest.request_type == "script",
            BlockedRequest.blocked.is_(True)
        )
        if filters:
            script_query = script_query.where(*filters)
        blocked_scripts = await self._scalar_count(session, script_query)

        classifications = ["Analytics", "Advertising", "Fingerprinting", "Suspicious"]
        class_counts = {}
        for cls in classifications:
            cls_query = select(func.count(BlockedRequest.id)).where(BlockedRequest.classification == cls)
            if filters:
                cls_query = cls_query.where(*filters)
            class_counts[cls.lower()] = await self._scalar_count(session, cls_query)

        if session.bind.dialect.name == "postgresql":
            date_expr = func.to_char(BlockedRequest.timestamp, "YYYY-MM-DD")
        else:
            date_expr = func.strftime("%Y-%m-%d", BlockedRequest.timestamp)

        over_time_query = select(
            date_expr.label("date"),
            func.count(BlockedRequest.id).label("count")
        )
        if filters:
            over_time_query = over_time_query.where(*filters)
        over_time_query = over_time_query.group_by("date").order_by("date")

        over_time_res = await session.execute(over_time_query)
        over_time = [{"date": row[0], "count": row[1]} for row in over_time_res.all()]

        type_query = select(
            BlockedRequest.request_type.label("type"),
            func.count(BlockedRequest.id).label("count")
        )
        if filters:
            type_query = type_query.where(*filters)
        type_query = type_query.group_by(BlockedRequest.request_type).order_by(func.count(BlockedRequest.id).desc())
        type_res = await session.execute(type_query)
        request_types = [{"type": row[0], "count": row[1]} for row in type_res.all()]

        risk_query = select(
            BlockedRequest.risk_score.label("risk_score"),
            func.count(BlockedRequest.id).label("count")
        )
        if filters:
            risk_query = risk_query.where(*filters)
        risk_query = risk_query.group_by(BlockedRequest.risk_score).order_by(BlockedRequest.risk_score)
        risk_res = await session.execute(risk_query)
        risk_distribution = [{"risk_score": row[0], "count": row[1]} for row in risk_res.all()]

        return {
            "total_requests": total_requests,
            "blocked_count": blocked_count,
            "observed_count": observed_count,
            "average_risk_score": average_risk_score,
            "blocked_scripts": blocked_scripts,
            "analytics": class_counts["analytics"],
            "advertising": class_counts["advertising"],
            "fingerprinting": class_counts["fingerprinting"],
            "suspicious": class_counts["suspicious"],
            "over_time": over_time,
            "request_types": request_types,
            "risk_distribution": risk_distribution
        }

    async def get_history_top_domains(
        self,
        session: AsyncSession,
        user_id: str | None = None,
        limit: int = 5
    ) -> list[dict]:
        filters = [BlockedRequest.blocked.is_(True)]
        if user_id:
            filters.append(BlockedRequest.user_id == user_id)

        query = select(
            BlockedRequest.domain,
            func.count(BlockedRequest.id).label("count")
        ).where(*filters).group_by(BlockedRequest.domain).order_by(func.count(BlockedRequest.id).desc()).limit(limit)

        result = await session.execute(query)
        return [{"domain": row[0], "count": row[1]} for row in result.all()]

    async def get_reputation(
        self,
        session: AsyncSession,
        limit: int = 50,
        offset: int = 0
    ) -> list[DomainReputation]:
        query = select(DomainReputation).order_by(DomainReputation.domain).offset(offset).limit(limit)
        result = await session.execute(query)
        return list(result.scalars().all())

    async def get_reputation_top_risk(
        self,
        session: AsyncSession,
        limit: int = 5
    ) -> list[DomainReputation]:
        query = select(DomainReputation).order_by(
            DomainReputation.average_risk_score.desc(),
            DomainReputation.times_blocked.desc()
        ).limit(limit)
        result = await session.execute(query)
        return list(result.scalars().all())

    async def get_reputation_by_domain(
        self,
        session: AsyncSession,
        domain: str
    ) -> DomainReputation | None:
        query = select(DomainReputation).where(DomainReputation.domain == domain)
        result = await session.execute(query)
        return result.scalar_one_or_none()
