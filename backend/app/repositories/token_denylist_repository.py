from datetime import datetime, timezone

from app.models.token_denylist import TokenDenylist
from app.repositories.base import BaseRepository


class TokenDenylistRepository(BaseRepository[TokenDenylist]):

    def is_denied(self, jti: str) -> bool:
        return self.db.query(TokenDenylist).filter(TokenDenylist.jti == jti).first() is not None

    def delete_expired(self, now: datetime | None = None) -> int:
        """Delete entries whose token already expired on its own — they no
        longer need denylisting. Called by the daily cleanup cron; without it
        the table grows without bound."""
        cutoff = now or datetime.now(timezone.utc)
        deleted = (
            self.db.query(TokenDenylist)
            .filter(TokenDenylist.expires_at < cutoff)
            .delete(synchronize_session=False)
        )
        self.db.commit()
        return deleted

    def save(self, entry: TokenDenylist) -> TokenDenylist:
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry
