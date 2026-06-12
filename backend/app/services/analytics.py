from datetime import datetime, timedelta, timezone

from sqlalchemy import Integer, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Install, TrackerEventRecord, User
from app.schemas.analytics import (
    BlockedScriptRecord,
    DomainCount,
    InstallTraffic,
    StatsResponse,
    TrackerEvent,
    TrackEventIn,
)
from app.services.classifier import TrackerClassifier


class AnalyticsService:
    """Database-backed analytics queries and writes."""

    def __init__(self, max_recent_events: int = 100) -> None:
        self._max_recent_events = max_recent_events

    async def ingest_event(
        self,
        session: AsyncSession,
        install: Install,
        event: TrackEventIn,
    ) -> StatsResponse:
        # Get count of events for this install and domain in the last 5 minutes (request frequency)
        time_limit = datetime.now(timezone.utc) - timedelta(minutes=5)
        count_query = select(func.count(TrackerEventRecord.id)).where(
            TrackerEventRecord.install_id == install.id,
            TrackerEventRecord.tracker_domain == event.tracker_domain,
            TrackerEventRecord.occurred_at >= time_limit
        )
        recent_count = await self._scalar_count(session, count_query)

        # Classify the threat level of the event
        classification = TrackerClassifier.classify(
            domain=event.tracker_domain,
            url=event.url,
            recent_count=recent_count,
            is_third_party=event.third_party,
        )

        record = TrackerEventRecord(
            install_id=install.id,
            tracker_domain=event.tracker_domain,
            url=event.url,
            page_origin=event.page_origin,
            request_type=event.request_type,
            source=event.source,
            blocked=event.blocked,
            third_party=event.third_party,
            classification=classification,
            occurred_at=event.occurred_at,
        )
        install.last_seen_at = datetime.now(timezone.utc)
        session.add(record)
        await session.commit()
        return await self.get_stats(session=session)

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
