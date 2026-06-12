from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db import get_db_session
from app.models import Install
from app.services.analytics import AnalyticsService
from app.services.auth import decode_admin_access_token, hash_token
from app.services.websocket_manager import WebSocketManager

bearer_scheme = HTTPBearer(auto_error=False)


def get_settings_dependency() -> Settings:
    return get_settings()


def get_analytics_service(request: Request) -> AnalyticsService:
    return request.app.state.analytics_service


def get_websocket_manager(request: Request) -> WebSocketManager:
    return request.app.state.websocket_manager


async def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings_dependency),
) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing admin authorization token.",
        )

    try:
        payload = decode_admin_access_token(credentials.credentials, settings)
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired admin token.",
        ) from error

    if payload.get("scope") not in ("admin", "user"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or user scope required.",
        )

    return payload


async def resolve_install_from_token(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> Install:
    install_token = request.headers.get("X-PhantomWall-Install-Token")
    if not install_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing install token.",
        )

    analytics_service = request.app.state.analytics_service
    install = await analytics_service.get_install_by_token(
        session=session,
        token_hash=hash_token(install_token),
    )
    if install is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid install token.",
        )
    return install
