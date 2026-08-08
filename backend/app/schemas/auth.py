import re
from datetime import datetime
from uuid import UUID

from pydantic import field_validator

from app.schemas._base import StrictModel, StrictORMModel
from app.utils.sanitize import strip_html, validate_url_scheme, validate_username

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_email(value: str) -> str:
    value = value.strip().lower()
    if not _EMAIL_RE.match(value) or len(value) > 254:
        raise ValueError("Invalid email address.")
    return value


def _validate_password(value: str) -> str:
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters long.")
    if len(value) > 128:
        raise ValueError("Password must be at most 128 characters long.")
    return value


class UserCreate(StrictModel):
    email: str
    username: str
    password: str
    full_name: str | None = None

    _email = field_validator("email")(staticmethod(_validate_email))
    _username = field_validator("username")(staticmethod(validate_username))
    _password = field_validator("password")(staticmethod(_validate_password))

    @field_validator("full_name")
    @classmethod
    def _clean_full_name(cls, v: str | None) -> str | None:
        return strip_html(v) if v is not None else None


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

    _email = field_validator("email")(staticmethod(_validate_email))


class ForgotPasswordRequest(StrictModel):
    email: str

    _email = field_validator("email")(staticmethod(_validate_email))


class ResetPasswordRequest(StrictModel):
    token: str
    new_password: str

    _password = field_validator("new_password")(staticmethod(_validate_password))


class OAuthLogin(StrictModel):
    email: str
    name: str | None = None
    avatar_url: str | None = None
    provider: str = "google"

    _email = field_validator("email")(staticmethod(_validate_email))

    @field_validator("name")
    @classmethod
    def _clean_name(cls, v: str | None) -> str | None:
        return strip_html(v) if v is not None else None

    @field_validator("avatar_url")
    @classmethod
    def _check_avatar_url(cls, v: str | None) -> str | None:
        return validate_url_scheme(v) if v is not None else None
