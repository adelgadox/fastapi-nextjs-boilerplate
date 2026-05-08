from app.models.token_denylist import TokenDenylist
from app.repositories.base import BaseRepository


class TokenDenylistRepository(BaseRepository[TokenDenylist]):

    def is_denied(self, jti: str) -> bool:
        return self.db.query(TokenDenylist).filter(TokenDenylist.jti == jti).first() is not None

    def save(self, entry: TokenDenylist) -> TokenDenylist:
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry
