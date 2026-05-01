from sqlalchemy import Column, String, DateTime
from app.database import Base


class TokenDenylist(Base):
    """Revoked JWT tokens (logout). Cleaned up after expiry."""
    __tablename__ = "token_denylist"

    jti = Column(String, primary_key=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
