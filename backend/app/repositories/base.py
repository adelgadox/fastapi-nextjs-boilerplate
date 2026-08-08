from typing import Generic, TypeVar

from sqlalchemy.orm import Query, Session

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """Abstract base for all repositories.

    Concrete repos inject a SQLAlchemy Session and expose named query methods
    so services never write raw db.query() calls.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def paginate(self, query: Query, limit: int, offset: int) -> tuple[list[T], int]:
        """Apply limit/offset to a query and return (items, total).

        `total` is counted before slicing so clients know whether more pages
        exist — pair with app.schemas.pagination.Page for the response shape.
        Always give the query a deterministic order (with a unique tiebreaker,
        e.g. `.order_by(Model.created_at.desc(), Model.id)`) before paginating,
        or rows can repeat/skip across pages.
        """
        total = query.order_by(None).count()
        items = query.limit(limit).offset(offset).all()
        return items, total
