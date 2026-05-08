import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models.token_denylist import TokenDenylist
from app.models.user import User
from app.repositories.token_denylist_repository import TokenDenylistRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import OAuthLogin, UserCreate
from app.services.base import BaseService
from app.utils.errors import api_error

logger = logging.getLogger(__name__)

_LOCKOUT_THRESHOLD = 10
_LOCKOUT_MINUTES = 15


class AuthService(BaseService):

    # ── Token / password helpers ───────────────────────────────────────────────

    @staticmethod
    def create_access_token(user_id: str) -> str:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
        jti = str(uuid.uuid4())
        return jwt.encode(
            {"sub": user_id, "exp": expire, "jti": jti},
            settings.secret_key,
            algorithm=settings.algorithm,
        )

    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        return bcrypt.checkpw(plain.encode(), hashed.encode())

    # ── Registration ───────────────────────────────────────────────────────────

    def register(
        self,
        data: UserCreate,
        background_tasks: BackgroundTasks,
        auto_verify: bool = False,
    ) -> dict:
        repo = UserRepository(self.db)
        if repo.email_exists(data.email):
            raise api_error("EMAIL_TAKEN", "Email already registered", field="email")
        if repo.username_exists(data.username):
            raise api_error("USERNAME_TAKEN", "Username already taken", field="username")

        token = secrets.token_urlsafe(32)
        user = repo.save(User(
            email=data.email,
            username=data.username,
            full_name=data.full_name,
            hashed_password=self.hash_password(data.password),
            is_verified=auto_verify,
            verification_token=None if auto_verify else token,
        ))

        if auto_verify:
            return {"message": "Registration successful.", "access_token": self.create_access_token(str(user.id))}

        # TODO: enqueue send_verification_email_task
        return {"message": "Registration successful. Check your email to verify your account."}

    # ── Login / logout ─────────────────────────────────────────────────────────

    def login(self, identifier: str, password: str) -> dict:
        user = UserRepository(self.db).find_active_by_identifier(identifier)

        if not user or not user.hashed_password:
            raise api_error("INVALID_CREDENTIALS", "Invalid credentials", status_code=401)

        now = datetime.now(timezone.utc)
        if user.lockout_until and user.lockout_until.replace(tzinfo=timezone.utc) > now:
            remaining = max(1, int((user.lockout_until.replace(tzinfo=timezone.utc) - now).total_seconds() // 60) + 1)
            raise api_error(
                "ACCOUNT_LOCKED",
                f"Too many failed attempts. Try again in {remaining} minute(s).",
                status_code=429,
            )

        if not self.verify_password(password, user.hashed_password):
            user.login_attempts = (user.login_attempts or 0) + 1
            if user.login_attempts >= _LOCKOUT_THRESHOLD:
                user.lockout_until = (datetime.now(timezone.utc) + timedelta(minutes=_LOCKOUT_MINUTES)).replace(tzinfo=None)
                user.login_attempts = 0
                self.db.commit()
                logger.warning("Account locked after %d failed attempts: user_id=%s", _LOCKOUT_THRESHOLD, user.id)
                raise api_error(
                    "ACCOUNT_LOCKED",
                    f"Too many failed attempts. Account locked for {_LOCKOUT_MINUTES} minutes.",
                    status_code=429,
                )
            self.db.commit()
            raise api_error("INVALID_CREDENTIALS", "Invalid credentials", status_code=401)

        user.login_attempts = 0
        user.lockout_until = None
        self.db.commit()

        if not user.is_active:
            raise api_error("ACCOUNT_DISABLED", "Account is disabled", status_code=403)
        if not user.is_verified:
            raise api_error("EMAIL_NOT_VERIFIED", "Email address not verified", status_code=403)

        return {"access_token": self.create_access_token(str(user.id)), "token_type": "bearer"}

    def logout(self, token: str) -> None:
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
            jti: str | None = payload.get("jti")
            exp: int | None = payload.get("exp")
            if jti and exp:
                expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
                repo = TokenDenylistRepository(self.db)
                if not repo.is_denied(jti):
                    repo.save(TokenDenylist(jti=jti, expires_at=expires_at))
        except jwt.PyJWTError:
            pass

    # ── Email verification ─────────────────────────────────────────────────────

    def verify_email(self, token: str) -> dict:
        repo = UserRepository(self.db)
        user = repo.find_by_verification_token(token)
        if not user:
            raise api_error("INVALID_VERIFICATION_TOKEN", "Invalid or expired verification link.")
        if user.is_verified:
            return {"message": "already_verified"}
        user.is_verified = True
        user.verification_token = None
        repo.commit()
        return {"message": "verified"}

    def resend_verification(self, email: str, background_tasks: BackgroundTasks) -> dict:
        repo = UserRepository(self.db)
        user = repo.find_by_email(email)
        if user and not user.is_verified:
            token = secrets.token_urlsafe(32)
            user.verification_token = token
            repo.commit()
            # TODO: enqueue send_verification_email_task
        return {"message": "If that email is registered and unverified, a new link is on its way."}

    # ── OAuth ──────────────────────────────────────────────────────────────────

    def oauth_login(self, data: OAuthLogin) -> dict:
        import re
        repo = UserRepository(self.db)
        user = repo.find_by_email(data.email)
        if not user:
            raw = data.email.split("@")[0]
            sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", raw)
            if not sanitized or not sanitized[0].isalnum():
                sanitized = "u" + sanitized
            base_username = sanitized[:28]
            username = base_username
            suffix = 1
            while repo.username_exists(username):
                username = f"{base_username}{suffix}"
                suffix += 1

            user = repo.save(User(
                email=data.email,
                username=username,
                full_name=data.name,
                avatar_url=data.avatar_url,
                is_verified=True,
                registered_provider=data.provider,
            ))

        return {"access_token": self.create_access_token(str(user.id)), "token_type": "bearer"}

    # ── Password reset ─────────────────────────────────────────────────────────

    def forgot_password(self, email: str, background_tasks: BackgroundTasks) -> dict:
        repo = UserRepository(self.db)
        user = repo.find_by_email(email)
        if user and user.hashed_password is not None:
            token = secrets.token_urlsafe(32)
            user.reset_password_token = token
            user.reset_password_token_expires_at = (
                datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
            )
            repo.commit()
            # TODO: enqueue send_password_reset_email_task
        return {"message": "If that email is registered, a reset link is on its way."}

    def reset_password(self, token: str, new_password: str, background_tasks: BackgroundTasks) -> dict:
        if len(new_password) < 8:
            raise api_error("PASSWORD_TOO_SHORT", "Password must be at least 8 characters.", field="new_password")
        if len(new_password) > 128:
            raise api_error("PASSWORD_TOO_LONG", "Password must be at most 128 characters.", field="new_password")

        repo = UserRepository(self.db)
        user = repo.find_by_reset_token(token)
        if not user or not user.reset_password_token_expires_at:
            raise api_error("INVALID_RESET_TOKEN", "Invalid or expired reset link.")
        if datetime.now(timezone.utc).replace(tzinfo=None) > user.reset_password_token_expires_at.replace(tzinfo=None):
            raise api_error("INVALID_RESET_TOKEN", "Invalid or expired reset link.")

        user.hashed_password = self.hash_password(new_password)
        user.reset_password_token = None
        user.reset_password_token_expires_at = None
        repo.commit()
        # TODO: enqueue send_password_changed_email_task
        return {"message": "Password updated successfully."}
