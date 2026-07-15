"""Issue / rotate / revoke refresh tokens.

Ported from pet-portal and adapted to this boilerplate's repository layering
and single-User owner model.

Flow:
- `issue`  → mint an opaque token, store only its hash, start a new family.
- `rotate` → validate + revoke the presented token, mint a successor in the
  same family. Reuse of an already-revoked token revokes the whole family.
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.services.base import BaseService


class RefreshError(Exception):
    """Raised when a refresh token cannot be rotated. `code` is a stable subcode
    consumed by the router to pick an HTTP status + error envelope."""

    def __init__(self, code: str, family_id: str | None = None) -> None:
        self.code = code
        self.family_id = family_id
        super().__init__(code)


def hash_refresh(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def _utcnow() -> datetime:
    """Naive UTC now (columns are naive DateTime), without the deprecated utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class RefreshTokenService(BaseService):
    def __init__(self, db: Session) -> None:
        super().__init__(db)
        self.repo = RefreshTokenRepository(db)

    def issue(self, user: User, *, device_id: str | None = None) -> str:
        """Mint a new refresh token for `user` and return the plaintext.
        Caller is responsible for committing the session."""
        plaintext = secrets.token_urlsafe(32)
        self.repo.add(RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh(plaintext),
            family_id=uuid.uuid4(),
            device_id=device_id,
            expires_at=_utcnow() + timedelta(days=settings.refresh_token_expire_days),
        ))
        return plaintext

    def rotate(self, plaintext: str, *, device_id: str | None = None) -> tuple[User, str]:
        """Validate the presented token, revoke it, and mint a successor in the
        same family. Returns (user, new_plaintext). Raises RefreshError on any
        invalid/expired/reused token. Caller commits."""
        row = self.repo.lock_by_hash(hash_refresh(plaintext))
        if row is None:
            raise RefreshError("invalid")
        if row.revoked_at is not None:
            # Reuse of an already-rotated/revoked token — revoke the whole chain.
            self.repo.revoke_family(row.family_id, _utcnow())
            raise RefreshError("token_reused", family_id=str(row.family_id))
        if row.expires_at < _utcnow():
            raise RefreshError("expired")

        user = self.db.get(User, row.user_id)
        if user is None or not user.is_active:
            raise RefreshError("invalid")

        row.revoked_at = _utcnow()
        new_plaintext = secrets.token_urlsafe(32)
        self.repo.add(RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh(new_plaintext),
            family_id=row.family_id,
            rotated_from=row.id,
            device_id=device_id if device_id is not None else row.device_id,
            expires_at=row.expires_at,  # not extended — the family has a hard lifetime
        ))
        return user, new_plaintext

    def revoke_by_plaintext(self, plaintext: str) -> None:
        """Revoke the family a token belongs to (used on logout). No-op if the
        token is unknown. Caller commits."""
        row = self.repo.find_by_hash(hash_refresh(plaintext))
        if row is not None:
            self.repo.revoke_family(row.family_id, _utcnow())

    def revoke_all_for_user(self, user: User) -> None:
        """Revoke every active refresh token for a user (e.g. password change)."""
        self.repo.revoke_all_for_user(user.id, _utcnow())
