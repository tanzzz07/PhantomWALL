from datetime import datetime, timezone

from sqlalchemy import Integer, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Install, TrackerEventRecord
from app.schemas.analytics import (
    DomainCount,
    InstallTraffic,
    StatsResponse,
    TrackerEvent,
    TrackEventIn,
)


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
        record = TrackerEventRecord(
            install_id=install.id,
            tracker_domain=event.tracker_domain,
            url=event.url,
            page_origin=event.page_origin,
            request_type=event.request_type,
            source=event.source,
            blocked=event.blocked,
            third_party=event.third_party,
            occurred_at=event.occurred_at,
        )
        install.last_seen_at = datetime.now(timezone.utc)
        session.add(record)
        await session.commit()
        return await self.get_stats(session=session)

    async def get_stats(
        self,
        session: AsyncSession,
        install_id: str | None = None,
        recent_limit: int | None = None,
    ) -> StatsResponse:
        base_filters = []
        if install_id:
            base_filters.append(TrackerEventRecord.install_id == install_id)

        total_events = await self._scalar_count(
            session,
            select(func.count(TrackerEventRecord.id)).where(*base_filters),
        )
        blocked_tracker_count = await self._scalar_count(
            session,
            select(func.count(TrackerEventRecord.id)).where(
                *base_filters,
                TrackerEventRecord.blocked.is_(True),
            ),
        )
        unique_tracker_count = await self._scalar_count(
            session,
            select(func.count(func.distinct(TrackerEventRecord.tracker_domain))).where(
                *base_filters
            ),
        )

        unique_install_count = await self._scalar_count(
            session,
            select(func.count(func.distinct(TrackerEventRecord.install_id))).where(
                *base_filters
            ),
        )

        top_tracker_domains = await self._top_domains(session, base_filters)
        request_type_breakdown = await self._request_type_breakdown(session, base_filters)
        installs = await self._install_breakdown(session, install_id)
        recent_events = await self._recent_events(
            session,
            base_filters,
            recent_limit or self._max_recent_events,
        )

        return StatsResponse(
            blocked_tracker_count=blocked_tracker_count,
            total_events=total_events,
            unique_tracker_count=unique_tracker_count,
            unique_install_count=unique_install_count,
            top_tracker_domains=top_tracker_domains,
            request_type_breakdown=request_type_breakdown,
            installs=installs,
            recent_events=recent_events,
            service_status="online",
            generated_at=datetime.now(timezone.utc),
            selected_install_id=install_id,
        )

    async def list_installs(self, session: AsyncSession) -> list[InstallTraffic]:
        return await self._install_breakdown(session=session, selected_install_id=None)

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
    ) -> Install:
        install = Install(
            display_name=display_name,
            token_hash=token_hash,
            extension_version=extension_version,
            browser_name=browser_name,
            notes=notes,
            last_seen_at=datetime.now(timezone.utc),
        )
        session.add(install)
        await session.commit()
        await session.refresh(install)
        return install

    async def _top_domains(
        self,
        session: AsyncSession,
        filters: list,
    ) -> list[DomainCount]:
        result = await session.execute(
            select(
                TrackerEventRecord.tracker_domain,
                func.count(TrackerEventRecord.id).label("count"),
            )
            .where(*filters)
            .group_by(TrackerEventRecord.tracker_domain)
            .order_by(func.count(TrackerEventRecord.id).desc())
            .limit(5)
        )
        return [
            DomainCount(domain=domain, count=count)
            for domain, count in result.all()
        ]

    async def _request_type_breakdown(
        self,
        session: AsyncSession,
        filters: list,
    ) -> list[DomainCount]:
        request_type_expr = func.coalesce(TrackerEventRecord.request_type, "unknown")
        result = await session.execute(
            select(
                request_type_expr.label("request_type"),
                func.count(TrackerEventRecord.id).label("count"),
            )
            .where(*filters)
            .group_by(request_type_expr)
            .order_by(func.count(TrackerEventRecord.id).desc())
            .limit(6)
        )
        return [
            DomainCount(domain=request_type, count=count)
            for request_type, count in result.all()
        ]

    async def _install_breakdown(
        self,
        session: AsyncSession,
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

    async def _recent_events(
        self,
        session: AsyncSession,
        filters: list,
        limit: int,
    ) -> list[TrackerEvent]:
        result = await session.execute(
            select(TrackerEventRecord)
            .options(selectinload(TrackerEventRecord.install))
            .where(*filters)
            .order_by(TrackerEventRecord.occurred_at.desc(), TrackerEventRecord.id.desc())
            .limit(limit)
        )
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
                occurred_at=record.occurred_at,
            )
            for record in records
        ]

    async def _scalar_count(self, session: AsyncSession, query: Select) -> int:
        result = await session.execute(query)
        return int(result.scalar() or 0)
