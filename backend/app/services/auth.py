import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import Settings


def hash_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def generate_install_token() -> str:
    return secrets.token_urlsafe(32)


def create_admin_access_token(settings: Settings) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=settings.admin_token_ttl_hours)
    payload = {
      "sub": settings.admin_username,
      "iat": int(now.timestamp()),
      "exp": int(expires_at.timestamp()),
      "scope": "admin",
    }
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return token, expires_at


def decode_admin_access_token(token: str, settings: Settings) -> dict:
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )

