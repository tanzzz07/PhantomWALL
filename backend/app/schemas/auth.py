from datetime import datetime

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class AdminIdentityResponse(BaseModel):
    username: str
    issued_at: datetime = Field(default_factory=datetime.utcnow)

