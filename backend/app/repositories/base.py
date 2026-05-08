from typing import Generic, TypeVar
from sqlalchemy.orm import Session

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """Abstract base for all repositories.

    Concrete repos inject a SQLAlchemy Session and expose named query methods
    so services never write raw db.query() calls.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
