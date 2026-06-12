from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    get_analytics_service,
    get_websocket_manager,
    require_admin,
    resolve_install_from_token,
)
from app.db import get_db_session
from app.models import Install
from app.schemas.analytics import BlockedScriptRecord, StatsResponse, TrackEventIn, TrackEventResponse
from app.services.analytics import AnalyticsService
from app.services.websocket_manager import WebSocketManager

router = APIRouter(tags=["analytics"])


@router.post(
    "/track-event",
    response_model=TrackEventResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def track_event(
    payload: TrackEventIn,
    install: Install = Depends(resolve_install_from_token),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    session: AsyncSession = Depends(get_db_session),
    websocket_manager: WebSocketManager = Depends(get_websocket_manager),
) -> TrackEventResponse:
    snapshot = await analytics_service.ingest_event(
        session=session,
        install=install,
        event=payload,
    )
    await websocket_manager.broadcast_json(
        {
            "type": "telemetry.received",
            "install_id": install.id,
            "tracker_domain": payload.tracker_domain,
        }
    )
    return TrackEventResponse(status="accepted", stats=snapshot)


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    install_id: str | None = Query(default=None),
    recent_limit: int = Query(default=25, ge=1, le=200),
    _admin: dict = Depends(require_admin),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    session: AsyncSession = Depends(get_db_session),
) -> StatsResponse:
    user_id = _admin.get("user_id") if _admin.get("scope") == "user" else None
    return await analytics_service.get_stats(
        session=session,
        user_id=user_id,
        install_id=install_id,
        recent_limit=recent_limit,
    )


@router.get("/blocked-scripts", response_model=list[BlockedScriptRecord])
async def get_blocked_scripts(
    install_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    _admin: dict = Depends(require_admin),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    session: AsyncSession = Depends(get_db_session),
) -> list[BlockedScriptRecord]:
    user_id = _admin.get("user_id") if _admin.get("scope") == "user" else None
    return await analytics_service.get_blocked_scripts(
        session=session,
        user_id=user_id,
        install_id=install_id,
        limit=limit,
    )

