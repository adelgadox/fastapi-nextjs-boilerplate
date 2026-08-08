from datetime import datetime, timezone
from uuid import UUID

from app.models.refresh_token import RefreshToken
from app.repositories.base import BaseRepository


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    """Refresh token data access — per-user session infrastructure."""

    def find_by_hash(self, token_hash: str) -> RefreshToken | None:
        return (
            self.db.query(RefreshToken)
            .filter(RefreshToken.token_hash == token_hash)
            .first()
        )

    def find_by_id(self, token_id: UUID) -> RefreshToken | None:
        return self.db.get(RefreshToken, token_id)

    def save(self, token: RefreshToken) -> RefreshToken:
        self.db.add(token)
        self.db.commit()
        self.db.refresh(token)
        return token

    def revoke_family(self, family_id: UUID) -> None:
        """Revoke every token of one family (one session).

        Used on logout and, above all, on reuse detection: if an
        already-rotated token reappeared, the whole chain is suspect and gets
        cut entirely.
        """
        self.db.query(RefreshToken).filter(
            RefreshToken.family_id == family_id,
            RefreshToken.revoked.is_(False),
        ).update({RefreshToken.revoked: True}, synchronize_session=False)
        self.db.commit()

    def delete_expired(self, now: datetime | None = None) -> int:
        """Delete expired tokens. Called by the cleanup cron."""
        cutoff = now or datetime.now(timezone.utc)
        deleted = (
            self.db.query(RefreshToken)
            .filter(RefreshToken.expires_at < cutoff)
            .delete(synchronize_session=False)
        )
        self.db.commit()
        return deleted
