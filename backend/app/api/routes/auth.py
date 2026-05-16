from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings
from app.core.dependencies import get_settings_dependency, require_admin
from app.schemas.auth import AdminIdentityResponse, AuthTokenResponse, LoginRequest
from app.services.auth import create_admin_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=AuthTokenResponse)
async def login(
    payload: LoginRequest,
    settings: Settings = Depends(get_settings_dependency),
) -> AuthTokenResponse:
    if (
        payload.username != settings.admin_username
        or payload.password != settings.admin_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials.",
        )

    token, expires_at = create_admin_access_token(settings)
    return AuthTokenResponse(access_token=token, expires_at=expires_at)


@router.get("/me", response_model=AdminIdentityResponse)
async def me(payload: dict = Depends(require_admin)) -> AdminIdentityResponse:
    return AdminIdentityResponse(
        username=payload["sub"],
        issued_at=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
    )
