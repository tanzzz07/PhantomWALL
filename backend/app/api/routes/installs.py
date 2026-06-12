from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.dependencies import (
    get_analytics_service,
    get_settings_dependency,
    require_admin,
)
from app.db import get_db_session
from app.models import User
from app.schemas.installs import (
    InstallListResponse,
    RegisterInstallRequest,
    RegisterInstallResponse,
)
from app.services.analytics import AnalyticsService
from app.services.auth import generate_install_token, hash_token

router = APIRouter(tags=["installs"])


@router.post("/installs/register", response_model=RegisterInstallResponse)
async def register_install(
    payload: RegisterInstallRequest,
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings_dependency),
) -> RegisterInstallResponse:
    if payload.invite_code != settings.registration_invite_code:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid invite code.",
        )

    user_id = None
    if payload.username:
        result = await session.execute(
            select(User).where(User.username == payload.username)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User '{payload.username}' not found. Please register on the dashboard first.",
            )
        user_id = user.id

    plain_token = generate_install_token()
    install = await analytics_service.create_install(
        session=session,
        display_name=payload.display_name.strip(),
        token_hash=hash_token(plain_token),
        extension_version=payload.extension_version,
        browser_name=payload.browser_name,
        notes=payload.notes,
        user_id=user_id,
    )
    return RegisterInstallResponse(
        install_id=install.id,
        display_name=install.display_name,
        api_token=plain_token,
        endpoint=settings.public_backend_url,
        created_at=install.created_at,
    )


@router.get("/installs", response_model=InstallListResponse)
async def list_installs(
    _admin: dict = Depends(require_admin),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    session: AsyncSession = Depends(get_db_session),
) -> InstallListResponse:
    user_id = _admin.get("user_id") if _admin.get("scope") == "user" else None
    installs = await analytics_service.list_installs(session=session, user_id=user_id)
    return InstallListResponse(installs=installs)

