import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import bcrypt
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.token_denylist import TokenDenylist
from app.utils.rate_limit import limiter

router = APIRouter(prefix="/auth", tags=["auth"])

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ── Helpers ────────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    jti = str(uuid.uuid4())
    return jwt.encode(
        {"sub": user_id, "exp": expire, "jti": jti},
        settings.secret_key,
        algorithm=settings.algorithm,
    )


# ── Schemas ────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    email: str
    username: str
    password: str
    full_name: str | None = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ResendRequest(BaseModel):
    email: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
async def register(
    request: Request,
    data: UserCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if db.query(User).filter(User.username == data.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")

    token = secrets.token_urlsafe(32)
    user = User(
        email=data.email,
        username=data.username,
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
        is_verified=False,
        verification_token=token,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # TODO: send verification email
    # background_tasks.add_task(send_verification_email, data.email, token)

    return {"message": "Registration successful. Check your email to verify your account."}


@router.post("/login", response_model=Token)
@limiter.limit("10/5minutes")
def login(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    identifier = form.username.strip()
    user = db.query(User).filter(
        (User.email == identifier) | (User.username == identifier)
    ).first()
    if not user or not user.hashed_password or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="ACCOUNT_DISABLED")
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="EMAIL_NOT_VERIFIED")
    return Token(access_token=create_access_token(str(user.id)))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
def logout(
    request: Request,
    token: str = Depends(_oauth2_scheme),
    db: Session = Depends(get_db),
) -> None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        jti: str | None = payload.get("jti")
        exp: int | None = payload.get("exp")
        if jti and exp:
            expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
            if not db.query(TokenDenylist).filter(TokenDenylist.jti == jti).first():
                db.add(TokenDenylist(jti=jti, expires_at=expires_at))
                db.commit()
    except jwt.PyJWTError:
        pass


@router.get("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.verification_token == token).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired verification link.")
    user.is_verified = True
    user.verification_token = None
    db.commit()
    return {"message": "verified"}


@router.post("/resend-verification")
@limiter.limit("3/hour")
async def resend_verification(
    request: Request,
    data: ResendRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == data.email).first()
    if user and not user.is_verified:
        token = secrets.token_urlsafe(32)
        user.verification_token = token
        db.commit()
        # TODO: background_tasks.add_task(send_verification_email, user.email, token)
    return {"message": "If that email is registered and unverified, a new link is on its way."}


@router.post("/forgot-password")
@limiter.limit("3/hour")
async def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == data.email).first()
    if user and user.hashed_password:
        token = secrets.token_urlsafe(32)
        user.reset_password_token = token
        user.reset_password_token_expires_at = (
            datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
        )
        db.commit()
        # TODO: background_tasks.add_task(send_password_reset_email, user.email, token)
    return {"message": "If that email is registered, a reset link is on its way."}


@router.post("/reset-password")
@limiter.limit("5/hour")
def reset_password(
    request: Request,
    data: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    if len(data.new_password) > 128:
        raise HTTPException(status_code=400, detail="Password must be at most 128 characters.")

    user = db.query(User).filter(User.reset_password_token == data.token).first()
    if not user or not user.reset_password_token_expires_at:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link.")
    if datetime.now(timezone.utc).replace(tzinfo=None) > user.reset_password_token_expires_at.replace(tzinfo=None):
        raise HTTPException(status_code=400, detail="Invalid or expired reset link.")

    user.hashed_password = hash_password(data.new_password)
    user.reset_password_token = None
    user.reset_password_token_expires_at = None
    db.commit()
    return {"message": "Password updated successfully."}
