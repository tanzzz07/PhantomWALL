from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.dependencies import get_settings_dependency, require_admin
from app.core.security import hash_password, verify_password
from app.db import get_db_session
from app.models import User
from app.schemas.auth import (
    AdminIdentityResponse,
    AuthTokenResponse,
    LoginRequest,
    UserRegisterRequest,
    UserRegisterResponse,
)
from app.services.auth import create_access_token, create_admin_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserRegisterRequest,
    session: AsyncSession = Depends(get_db_session),
) -> UserRegisterResponse:
    result = await session.execute(
        select(User).where(User.username == payload.username)
    )
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered.",
        )

    pw_hash = hash_password(payload.password)
    user = User(
        username=payload.username,
        password_hash=pw_hash,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    return UserRegisterResponse(
        id=user.id,
        username=user.username,
        created_at=user.created_at,
    )


@router.post("/login", response_model=AuthTokenResponse)
async def login(
    payload: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings_dependency),
) -> AuthTokenResponse:
    # Check admin settings credentials
    if (
        payload.username == settings.admin_username
        and payload.password == settings.admin_password
    ):
        token, expires_at = create_admin_access_token(settings)
        return AuthTokenResponse(access_token=token, expires_at=expires_at)

    # Check database users
    result = await session.execute(
        select(User).where(User.username == payload.username)
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    token, expires_at = create_access_token(
        username=user.username,
        settings=settings,
        scope="user",
        user_id=user.id,
    )
    return AuthTokenResponse(access_token=token, expires_at=expires_at)


@router.get("/me", response_model=AdminIdentityResponse)
async def me(payload: dict = Depends(require_admin)) -> AdminIdentityResponse:
    return AdminIdentityResponse(
        username=payload["sub"],
        issued_at=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
    )

