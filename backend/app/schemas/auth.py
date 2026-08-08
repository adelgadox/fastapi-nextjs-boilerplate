from datetime import datetime
from uuid import UUID

from app.schemas._base import StrictModel, StrictORMModel


class UserCreate(StrictModel):
    email: str
    username: str
    password: str
    full_name: str | None = None


class Token(StrictModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    # Access token lifetime in seconds — lets clients (especially mobile)
    # schedule renewal without decoding the JWT.
    expires_in: int | None = None


class RefreshRequest(StrictModel):
    refresh_token: str


class LogoutRequest(StrictModel):
    # Optional: when the client sends it, the whole refresh family (that
    # session) is revoked, not just the current access token. The access token
    # is always revoked via its jti.
    refresh_token: str | None = None


class UserOut(StrictORMModel):
    id: UUID
    email: str
    username: str
    full_name: str | None = None
    avatar_url: str | None = None
    role: str
    plan: str
    is_verified: bool
    created_at: datetime


class ResendRequest(StrictModel):
    email: str


class ForgotPasswordRequest(StrictModel):
    email: str


class ResetPasswordRequest(StrictModel):
    token: str
    new_password: str


class OAuthLogin(StrictModel):
    email: str
    name: str | None = None
    avatar_url: str | None = None
    provider: str = "google"
