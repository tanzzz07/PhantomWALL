from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PHANTOMWALL_",
        case_sensitive=False,
    )

    app_name: str = "PhantomWall Backend"
    app_env: str = "development"
    database_url: str = (
        "postgresql+asyncpg://phantomwall:phantomwall@postgres:5432/phantomwall"
    )
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost", "http://127.0.0.1"]
    )
    cors_origin_regex: str = r"chrome-extension://.*"
    max_recent_events: int = 100
    admin_username: str = "admin"
    admin_password: str = "change-this-password"
    admin_token_ttl_hours: int = 12
    jwt_secret_key: str = "change-this-jwt-secret"
    jwt_algorithm: str = "HS256"
    registration_invite_code: str = "phantomwall-invite"
    public_backend_url: str = "http://localhost:8000"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return ["http://localhost", "http://127.0.0.1"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
