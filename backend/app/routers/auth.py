from fastapi import APIRouter, BackgroundTasks, Body, Depends, Header, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_internal_token
from app.schemas.auth import (
    ForgotPasswordRequest,
    OAuthLogin,
    RefreshRequest,
    ResendRequest,
    ResetPasswordRequest,
    Token,
    UserCreate,
)
from app.services.auth_service import AuthService
from app.services.refresh_token_service import RefreshError
from app.utils.errors import api_error
from app.utils.rate_limit import limiter

router = APIRouter(prefix="/auth", tags=["auth"])

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login")


@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
async def register(
    request: Request,
    data: UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    return AuthService(db).register(data, background_tasks)


@router.post("/login", response_model=Token)
@limiter.limit("10/5minutes")
def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    x_device_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    return AuthService(db).login(form.username.strip(), form.password, device_id=x_device_id)


_REFRESH_ERROR = {
    "invalid": (401, "INVALID_REFRESH_TOKEN", "Invalid session. Please sign in again."),
    "token_reused": (401, "TOKEN_REUSED", "Session revoked for security. Please sign in again."),
    "expired": (401, "REFRESH_EXPIRED", "Session expired. Please sign in again."),
}


@router.post("/refresh", response_model=Token)
@limiter.limit("30/minute")
def refresh(
    request: Request,
    data: RefreshRequest,
    db: Session = Depends(get_db),
):
    try:
        return AuthService(db).refresh(data.refresh_token, device_id=data.device_id)
    except RefreshError as exc:
        # Persist any family revocation triggered by reuse-detection before erroring.
        db.commit()
        status_code, code, message = _REFRESH_ERROR[exc.code]
        raise api_error(code, message, status_code=status_code)


@router.post("/oauth", response_model=Token, dependencies=[Depends(require_internal_token)])
@limiter.limit("10/5minutes")
def oauth_login(
    request: Request,
    data: OAuthLogin,
    db: Session = Depends(get_db),
):
    """Server-to-server only. The Next.js server verifies the OAuth provider,
    then calls this with the shared ``X-Internal-Token`` header. Never expose
    this endpoint to browsers/mobile clients directly — it mints access tokens."""
    return AuthService(db).oauth_login(data)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
def logout(
    request: Request,
    token: str = Depends(_oauth2_scheme),
    refresh_token: str | None = Body(default=None, embed=True),
    db: Session = Depends(get_db),
) -> None:
    AuthService(db).logout(token, refresh_token)


@router.get("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)):
    return AuthService(db).verify_email(token)


@router.post("/resend-verification")
@limiter.limit("3/hour")
async def resend_verification(
    request: Request,
    data: ResendRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    return AuthService(db).resend_verification(data.email, background_tasks)


@router.post("/forgot-password")
@limiter.limit("3/hour")
async def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    return AuthService(db).forgot_password(data.email, background_tasks)


@router.post("/reset-password")
@limiter.limit("5/hour")
def reset_password(
    request: Request,
    data: ResetPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    return AuthService(db).reset_password(data.token, data.new_password, background_tasks)
