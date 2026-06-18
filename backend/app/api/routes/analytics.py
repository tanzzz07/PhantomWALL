from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    get_analytics_service,
    get_websocket_manager,
    require_admin,
    resolve_install_from_token,
)
from app.db import get_db_session
from app.models import Install
from app.schemas.analytics import (
    BlockedScriptRecord, 
    StatsResponse, 
    TrackEventIn, 
    TrackEventResponse,
    HistoryResponse,
    HistoryStatsResponse,
    DomainReputationSchema
)
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
    snapshot, blocked_record = await analytics_service.ingest_event(
        session=session,
        install=install,
        event=payload,
    )

    domain = payload.domain or payload.tracker_domain or "unknown"

    # Broadcast new real-time structured event for History and Reputation panel
    await websocket_manager.broadcast_json(
        {
            "type": "history.new",
            "domain": blocked_record.domain,
            "classification": blocked_record.classification,
            "confidence": blocked_record.confidence,
            "risk_score": blocked_record.risk_score,
            "blocked": blocked_record.blocked,
        }
    )

    # Legacy WebSocket broadcast compatibility
    await websocket_manager.broadcast_json(
        {
            "type": "telemetry.received",
            "install_id": install.id,
            "tracker_domain": domain,
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


@router.get("/history", response_model=HistoryResponse)
async def get_history(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=500),
    classification: str | None = Query(default=None),
    request_type: str | None = Query(default=None),
    search: str | None = Query(default=None),
    _admin: dict = Depends(require_admin),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    user_id = _admin.get("user_id") if _admin.get("scope") == "user" else None
    return await analytics_service.get_history(
        session=session,
        user_id=user_id,
        page=page,
        limit=limit,
        classification=classification,
        request_type=request_type,
        search=search,
    )


@router.get("/history/stats", response_model=HistoryStatsResponse)
async def get_history_stats(
    _admin: dict = Depends(require_admin),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    user_id = _admin.get("user_id") if _admin.get("scope") == "user" else None
    return await analytics_service.get_history_stats(
        session=session,
        user_id=user_id,
    )


@router.get("/history/top-domains", response_model=list[dict])
async def get_history_top_domains(
    limit: int = Query(default=5, ge=1, le=50),
    _admin: dict = Depends(require_admin),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    user_id = _admin.get("user_id") if _admin.get("scope") == "user" else None
    return await analytics_service.get_history_top_domains(
        session=session,
        user_id=user_id,
        limit=limit,
    )


@router.get("/reputation", response_model=list[DomainReputationSchema])
async def get_reputation(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _admin: dict = Depends(require_admin),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    session: AsyncSession = Depends(get_db_session),
) -> list:
    return await analytics_service.get_reputation(
        session=session,
        limit=limit,
        offset=offset,
    )


@router.get("/reputation/top-risk", response_model=list[DomainReputationSchema])
async def get_reputation_top_risk(
    limit: int = Query(default=5, ge=1, le=50),
    _admin: dict = Depends(require_admin),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    session: AsyncSession = Depends(get_db_session),
) -> list:
    return await analytics_service.get_reputation_top_risk(
        session=session,
        limit=limit,
    )


@router.get("/reputation/domain/{domain}", response_model=DomainReputationSchema | None)
async def get_reputation_by_domain(
    domain: str,
    _admin: dict = Depends(require_admin),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    session: AsyncSession = Depends(get_db_session),
):
    return await analytics_service.get_reputation_by_domain(
        session=session,
        domain=domain,
    )


@router.post("/admin/cleanup")
async def manual_cleanup(
    _admin: dict = Depends(require_admin),
) -> dict:
    from app.db import engine
    from app.services.retention import run_retention_cleanup
    if _admin.get("scope") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required."
        )
    return await run_retention_cleanup(engine)
