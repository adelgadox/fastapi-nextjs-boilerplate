"""Long-lived refresh tokens with rotation + reuse detection.

Ported from pet-portal (`refresh_token_service.py`) and adapted to this
boilerplate (single `User` owner, UUID ids).

Only the sha256 hash of the opaque token is stored — never the plaintext.
Rotation revokes the presented row and issues a new one in the same
`family_id`; presenting an already-rotated (revoked) token — a "reuse" — is
treated as theft and revokes the whole family. See RefreshTokenService.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # sha256 hex of the opaque token — the plaintext is never stored.
    token_hash = Column(String(64), unique=True, index=True, nullable=False)
    # All tokens rotated from one login share a family_id; reuse revokes the family.
    family_id = Column(UUID(as_uuid=True), index=True, nullable=False)
    rotated_from = Column(
        UUID(as_uuid=True),
        ForeignKey("refresh_tokens.id", ondelete="SET NULL"),
        nullable=True,
    )
    device_id = Column(String(255), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
