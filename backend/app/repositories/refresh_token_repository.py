"""Data access for refresh tokens — no business logic lives here."""

from datetime import datetime

from app.models.refresh_token import RefreshToken
from app.repositories.base import BaseRepository


class RefreshTokenRepository(BaseRepository[RefreshToken]):

    def add(self, token: RefreshToken) -> RefreshToken:
        self.db.add(token)
        return token

    def find_by_hash(self, token_hash: str) -> RefreshToken | None:
        return (
            self.db.query(RefreshToken)
            .filter(RefreshToken.token_hash == token_hash)
            .first()
        )

    def lock_by_hash(self, token_hash: str) -> RefreshToken | None:
        """Fetch a token FOR UPDATE — serializes concurrent rotation of the same
        token so a replayed (already-rotated) token fails safe as reuse instead
        of racing another transaction under READ COMMITTED."""
        return (
            self.db.query(RefreshToken)
            .filter(RefreshToken.token_hash == token_hash)
            .with_for_update()
            .first()
        )

    def revoke_family(self, family_id, now: datetime) -> None:
        self.db.query(RefreshToken).filter(
            RefreshToken.family_id == family_id,
            RefreshToken.revoked_at.is_(None),
        ).update({RefreshToken.revoked_at: now}, synchronize_session=False)

    def revoke_all_for_user(self, user_id, now: datetime) -> None:
        self.db.query(RefreshToken).filter(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        ).update({RefreshToken.revoked_at: now}, synchronize_session=False)
