from datetime import datetime

from pydantic import BaseModel


class RegisterInstallRequest(BaseModel):
    display_name: str
    invite_code: str
    extension_version: str | None = None
    browser_name: str | None = "Chrome"
    notes: str | None = None


class RegisterInstallResponse(BaseModel):
    install_id: str
    display_name: str
    api_token: str
    endpoint: str
    created_at: datetime


class InstallSummary(BaseModel):
    install_id: str
    display_name: str
    event_count: int
    blocked_count: int
    last_seen_at: datetime | None = None


class InstallListResponse(BaseModel):
    installs: list[InstallSummary]

