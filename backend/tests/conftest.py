"""Test harness — runs against a real PostgreSQL (never SQLite), because the
models use the postgresql UUID type. Each test runs inside a transaction that is
rolled back at the end, so tests are isolated even though services call commit().

Requires a reachable Postgres. Locally: `docker-compose up -d db` then
    createdb app_test  (or let CI provision it)
Point TEST_DATABASE_URL at it (defaults to the docker-compose db + `app_test`).
"""

import os

# Settings are read at import time, so the required env must exist first.
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get("TEST_DATABASE_URL", "postgresql://app:app@localhost:5432/app_test"),
)
os.environ.setdefault("DATABASE_URL_DIRECT", os.environ["DATABASE_URL"])
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-bytes-long-000000")
os.environ.setdefault("INTERNAL_API_SECRET", "test-internal-secret")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# Import every model so create_all builds the full schema.
import app.models.user  # noqa: F401,E402
import app.models.token_denylist  # noqa: F401,E402
import app.models.refresh_token  # noqa: F401,E402
from app.database import Base, get_db
# Aliased: the package is named `app`, so importing the FastAPI instance as
# `app` would be shadowed by the `import app.models.*` statements above.
from app.main import app as fastapi_app

_engine = create_engine(os.environ["DATABASE_URL"])


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.create_all(_engine)
    yield
    Base.metadata.drop_all(_engine)


@pytest.fixture
def db():
    """A session bound to a transaction rolled back after the test. Inner
    commit()s become savepoints, so nothing leaks between tests."""
    connection = _engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db):
    fastapi_app.dependency_overrides[get_db] = lambda: db
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()
