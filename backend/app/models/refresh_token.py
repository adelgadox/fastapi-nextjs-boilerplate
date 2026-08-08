import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RefreshToken(Base):
    """Rotating refresh token, one row per issued token.

    The raw token is never stored: only its SHA-256 (`token_hash`). A database
    leak does not hand out usable tokens.

    **Rotation with reuse detection.** Every use of `/auth/refresh` marks the
    current token as `revoked`, points `replaced_by` at the new one and issues
    another with the same `family_id`. If an already-revoked token shows up
    later, that signals theft: someone cloned the chain. The response is to
    revoke the whole family — attacker and victim are both locked out — and
    force a fresh login.

    `family_id` groups the entire chain born from one login; revoking by family
    kills that session without touching the others (another device stays alive).
    """

    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash = Column(String, nullable=False, unique=True, index=True)
    family_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, nullable=False, default=False)
    # Points at the token that replaced this one on rotation; NULL while current.
    replaced_by = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
