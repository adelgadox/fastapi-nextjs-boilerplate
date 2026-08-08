import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.orm import Session

from app.arq_pool import enqueue
from app.config import settings
from app.models.refresh_token import RefreshToken
from app.models.token_denylist import TokenDenylist
from app.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.token_denylist_repository import TokenDenylistRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import OAuthLogin, UserCreate
from app.services.base import BaseService
from app.utils.errors import api_error

logger = logging.getLogger(__name__)

_LOCKOUT_THRESHOLD = 10
_LOCKOUT_MINUTES = 15
# Pre-computed dummy hash used for constant-time rejection of unknown users
_DUMMY_HASH = bcrypt.hashpw(b"__dummy_sentinel__", bcrypt.gensalt()).decode()


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

    # ── Refresh tokens ──────────────────────────────────────────────────────────

    @staticmethod
    def _hash_refresh_token(raw: str) -> str:
        """SHA-256 of the raw token. Only the hash ever touches the database."""
        return hashlib.sha256(raw.encode()).hexdigest()

    def _create_refresh_token(self, user_id: uuid.UUID, family_id: uuid.UUID | None = None) -> str:
        """Create a refresh token and return the raw value (never stored).

        `family_id` None starts a new family (one login); passing one continues
        the existing chain on rotation.
        """
        raw = secrets.token_urlsafe(48)
        row = RefreshToken(
            user_id=user_id,
            token_hash=self._hash_refresh_token(raw),
            family_id=family_id or uuid.uuid4(),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
        )
        RefreshTokenRepository(self.db).save(row)
        return raw

    def _issue_session(self, user: User) -> dict:
        """Full session response: short access + long-lived refresh.

        The single place where it's assembled; login and oauth_login share it
        so they never diverge. `expires_in` (seconds) lets clients schedule
        renewal without decoding the JWT.
        """
        return {
            "access_token": self.create_access_token(str(user.id)),
            "refresh_token": self._create_refresh_token(user.id),
            "token_type": "bearer",
            "expires_in": settings.access_token_expire_minutes * 60,
        }

    def _is_benign_reuse(self, repo: RefreshTokenRepository, row: RefreshToken) -> bool:
        """True when reusing this revoked token is a client double-fire.

        Benign if it was replaced very recently (grace window) and its
        replacement is still live: two renewals that went out almost at once.
        A later reuse, or one where the chain already moved on (the replacement
        was also revoked), is suspect and doesn't enter here.
        """
        if row.replaced_by is None:
            return False
        replacement = repo.find_by_id(row.replaced_by)
        if replacement is None or replacement.revoked or replacement.created_at is None:
            return False
        leeway = timedelta(seconds=settings.refresh_reuse_leeway_seconds)
        return datetime.now(timezone.utc) - replacement.created_at.replace(tzinfo=timezone.utc) <= leeway

    def refresh(self, raw_token: str) -> dict:
        """Rotate a refresh token: issue a new one and revoke the presented one.

        Reuse detection: if the presented token was already revoked, someone
        reused an old link of the chain — a theft signal — and the entire
        family is revoked. An expired or unknown token is a normal 401.
        """
        repo = RefreshTokenRepository(self.db)
        row = repo.find_by_hash(self._hash_refresh_token(raw_token))
        if row is None:
            raise api_error("INVALID_REFRESH_TOKEN", "Invalid refresh token", status_code=401)

        if row.revoked:
            if not self._is_benign_reuse(repo, row):
                # Real reuse of an old token: cut the whole session.
                repo.revoke_family(row.family_id)
                raise api_error("REFRESH_TOKEN_REUSED", "Refresh token reuse detected", status_code=401)
            # Concurrent client double-fire inside the grace window: not theft.
            # Continue and issue a fresh rotation.

        if row.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            raise api_error("REFRESH_TOKEN_EXPIRED", "Refresh token expired", status_code=401)

        user = UserRepository(self.db).find_by_id(row.user_id)
        if user is None or not user.is_active:
            raise api_error("INVALID_REFRESH_TOKEN", "Invalid refresh token", status_code=401)

        # Rotate within the same family and chain the replacement.
        new_raw = self._create_refresh_token(user.id, family_id=row.family_id)
        new_row = repo.find_by_hash(self._hash_refresh_token(new_raw))
        row.revoked = True
        row.replaced_by = new_row.id if new_row else None
        self.db.commit()

        return {
            "access_token": self.create_access_token(str(user.id)),
            "refresh_token": new_raw,
            "token_type": "bearer",
            "expires_in": settings.access_token_expire_minutes * 60,
        }

    def revoke_refresh_token(self, raw_token: str) -> None:
        """Revoke a refresh token's family (logout). Silent when the token
        doesn't exist: logging out must not leak whether it was valid."""
        repo = RefreshTokenRepository(self.db)
        row = repo.find_by_hash(self._hash_refresh_token(raw_token))
        if row is not None:
            repo.revoke_family(row.family_id)

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

        enqueue(background_tasks, "send_verification_email_task", user.email, token)
        return {"message": "Registration successful. Check your email to verify your account."}

    # ── Login / logout ─────────────────────────────────────────────────────────

    def login(self, identifier: str, password: str) -> dict:
        user = UserRepository(self.db).find_active_by_identifier(identifier)

        if not user or not user.hashed_password:
            # Constant-time response: always run bcrypt to prevent timing oracle
            bcrypt.checkpw(password.encode(), _DUMMY_HASH.encode())
            raise api_error("INVALID_CREDENTIALS", "Invalid credentials", status_code=401)

        # Check account status before spending time on bcrypt
        if not user.is_active:
            raise api_error("ACCOUNT_DISABLED", "Account is disabled", status_code=403)

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

        if not user.is_verified:
            raise api_error("EMAIL_NOT_VERIFIED", "Email address not verified", status_code=403)

        return self._issue_session(user)

    def logout(self, token: str, refresh_token: str | None = None) -> None:
        # Revoke the refresh family so a leaked token doesn't outlive the
        # session; the access token is invalidated by its jti below.
        if refresh_token:
            self.revoke_refresh_token(refresh_token)
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
            enqueue(background_tasks, "send_verification_email_task", user.email, token)
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

        return self._issue_session(user)

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
            enqueue(background_tasks, "send_password_reset_email_task", user.email, token)
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
        # Optional: a "password changed" confirmation email — see roadmap phase-01.
        return {"message": "Password updated successfully."}
