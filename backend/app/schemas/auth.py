from app.schemas._base import StrictModel


class UserCreate(StrictModel):
    email: str
    username: str
    password: str
    full_name: str | None = None


class Token(StrictModel):
    access_token: str
    token_type: str = "bearer"


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
