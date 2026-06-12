import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import Settings


def hash_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def generate_install_token() -> str:
    return secrets.token_urlsafe(32)


def create_access_token(username: str, settings: Settings, scope: str = "user", user_id: str | None = None) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=settings.admin_token_ttl_hours)
    payload = {
      "sub": username,
      "iat": int(now.timestamp()),
      "exp": int(expires_at.timestamp()),
      "scope": scope,
    }
    if user_id:
        payload["user_id"] = user_id
    token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return token, expires_at



def create_admin_access_token(settings: Settings) -> tuple[str, datetime]:
    return create_access_token(settings.admin_username, settings, "admin")


def decode_admin_access_token(token: str, settings: Settings) -> dict:
    return jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )


