"""Refresh tokens: rotation, reuse detection, and logout.

What these tests pin down is not just that renewal works, but what it
protects: a rotated token cannot be used again, and if someone tries, the
whole session falls (not just that token). It's the difference between
"a token was stolen" and "they have indefinite access".
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.refresh_token import RefreshToken
from app.services.auth_service import AuthService


@pytest.fixture
def db():
    from app.models import refresh_token, token_denylist, user  # noqa: F401

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    yield session
    session.close()


@pytest.fixture
def user(db):
    from app.models.user import User

    u = User(
        id=uuid.uuid4(),
        email="v@example.com",
        username="v",
        hashed_password="x",
        is_active=True,
        is_verified=True,
    )
    db.add(u)
    db.commit()
    return u


def _hash(raw: str) -> str:
    return AuthService._hash_refresh_token(raw)


def test_a_session_issues_both_tokens(db, user):
    session = AuthService(db)._issue_session(user)
    assert session["access_token"]
    assert session["refresh_token"]
    assert session["expires_in"] > 0
    # The raw value never lives in the database: only its hash.
    assert db.query(RefreshToken).filter_by(token_hash=_hash(session["refresh_token"])).one()


def test_refresh_rotates_and_revokes_the_old_token(db, user):
    first = AuthService(db)._issue_session(user)["refresh_token"]

    rotated = AuthService(db).refresh(first)
    assert rotated["access_token"]
    assert rotated["refresh_token"] != first

    old = db.query(RefreshToken).filter_by(token_hash=_hash(first)).one()
    assert old.revoked is True
    assert old.replaced_by is not None


def test_reusing_an_old_token_after_the_chain_moved_kills_the_family(db, user):
    # Real theft: the chain already advanced twice, so reusing the first link
    # is not a concurrent double-fire but a resurrected old token.
    first = AuthService(db)._issue_session(user)["refresh_token"]
    second = AuthService(db).refresh(first)["refresh_token"]
    third = AuthService(db).refresh(second)["refresh_token"]

    with pytest.raises(HTTPException) as exc:
        AuthService(db).refresh(first)
    assert exc.value.detail["code"] == "REFRESH_TOKEN_REUSED"

    # The whole family is revoked: the current token no longer works either.
    with pytest.raises(HTTPException):
        AuthService(db).refresh(third)


def test_a_concurrent_double_refresh_is_tolerated(db, user):
    # Two client surfaces renew almost at once with the same token: the second
    # arrives after rotation, but inside the grace window and with the
    # replacement still live. Not theft: tolerated, session survives.
    first = AuthService(db)._issue_session(user)["refresh_token"]
    AuthService(db).refresh(first)  # rotates; replacement is live and fresh

    again = AuthService(db).refresh(first)  # same token, double fire
    assert again["access_token"]
    assert again["refresh_token"]


def test_an_expired_refresh_token_is_rejected(db, user):
    raw = AuthService(db)._issue_session(user)["refresh_token"]
    row = db.query(RefreshToken).filter_by(token_hash=_hash(raw)).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        AuthService(db).refresh(raw)
    assert exc.value.detail["code"] == "REFRESH_TOKEN_EXPIRED"


def test_an_unknown_refresh_token_is_rejected(db, user):
    with pytest.raises(HTTPException) as exc:
        AuthService(db).refresh("nope-not-a-real-token")
    assert exc.value.detail["code"] == "INVALID_REFRESH_TOKEN"


def test_logout_revokes_the_refresh_family(db, user):
    raw = AuthService(db)._issue_session(user)["refresh_token"]

    AuthService(db).logout("not-a-jwt-access", refresh_token=raw)

    with pytest.raises(HTTPException):
        AuthService(db).refresh(raw)


def test_a_disabled_user_cannot_refresh(db, user):
    raw = AuthService(db)._issue_session(user)["refresh_token"]
    user.is_active = False
    db.commit()

    with pytest.raises(HTTPException) as exc:
        AuthService(db).refresh(raw)
    assert exc.value.detail["code"] == "INVALID_REFRESH_TOKEN"
