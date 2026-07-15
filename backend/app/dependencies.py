import secrets

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import jwt

from app.database import get_db
from app.config import settings
from app.models.user import User
from app.repositories.token_denylist_repository import TokenDenylistRepository
from app.repositories.user_repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login")


def require_internal_token(x_internal_token: str | None = Header(default=None)) -> None:
    """Guard server-to-server endpoints with the shared internal secret.

    Fail-closed: when ``internal_api_secret`` is unset the endpoint is blocked
    entirely, because these routes can mint access tokens or bypass verification.
    The Next.js server (which has verified the upstream OAuth provider) must send
    the ``X-Internal-Token`` header. Constant-time compare avoids timing leaks.
    """
    expected = settings.internal_api_secret
    forbidden = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"code": "FORBIDDEN", "message": "Internal access required", "field": None, "meta": None},
    )
    if not expected or not x_internal_token:
        raise forbidden
    if not secrets.compare_digest(x_internal_token, expected):
        raise forbidden


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "UNAUTHORIZED", "message": "Could not validate credentials", "field": None, "meta": None},
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: str = payload.get("sub")
        jti: str | None = payload.get("jti")
        if user_id is None or jti is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception

    if TokenDenylistRepository(db).is_denied(jti):
        raise credentials_exception

    user = UserRepository(db).find_by_id(user_id)
    if not user:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "ACCOUNT_DISABLED", "message": "Account is disabled", "field": None, "meta": None},
        )

    return user


def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ("admin", "superadmin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Admin access required", "field": None, "meta": None},
        )
    return current_user


def get_current_superadmin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Superadmin access required", "field": None, "meta": None},
        )
    return current_user
