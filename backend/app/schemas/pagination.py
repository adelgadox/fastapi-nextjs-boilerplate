"""Generic pagination envelope.

One list contract for every client (web and mobile): `items` plus enough
metadata to know whether more pages exist without the "got fewer than limit"
guess. Use it on every list endpoint instead of returning a bare array —
mixing the two shapes forces each client screen to special-case.

Usage::

    from app.schemas.pagination import Page

    @router.get("/widgets", response_model=Page[WidgetOut])
    def list_widgets(
        request: Request,
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
        db: Session = Depends(get_db),
    ):
        items, total = WidgetRepository(db).paginate(query, limit, offset)
        return Page(items=items, total=total, limit=limit, offset=offset)
"""

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    # from_attributes so `items` can hold ORM objects serialized through the
    # item schema; strict coercion rules come from the item schema itself.
    model_config = ConfigDict(from_attributes=True)

    items: list[T]
    total: int
    limit: int
    offset: int
