"""Shared base models with Pydantic v2 strict mode enabled globally.

StrictModel      — for input schemas (request bodies, query params)
StrictORMModel   — for output schemas mapped from SQLAlchemy ORM objects
"""

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True)


class StrictORMModel(BaseModel):
    model_config = ConfigDict(strict=True, from_attributes=True)
