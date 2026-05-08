from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.auth import ForgotPasswordRequest, OAuthLogin, ResendRequest, ResetPasswordRequest, Token, UserCreate
from app.services.auth_service import AuthService
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
    db: Session = Depends(get_db),
):
    return AuthService(db).login(form.username.strip(), form.password)


@router.post("/oauth", response_model=Token)
@limiter.limit("10/5minutes")
def oauth_login(
    request: Request,
    data: OAuthLogin,
    db: Session = Depends(get_db),
):
    return AuthService(db).oauth_login(data)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
def logout(
    request: Request,
    token: str = Depends(_oauth2_scheme),
    db: Session = Depends(get_db),
) -> None:
    AuthService(db).logout(token)


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
