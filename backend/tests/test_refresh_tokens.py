"""Refresh-token rotation + reuse detection (roadmap phase-01)."""

from datetime import datetime, timedelta, timezone

import pytest

from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services.auth_service import AuthService
from app.services.refresh_token_service import (
    RefreshError,
    RefreshTokenService,
    hash_refresh,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _make_user(db, *, verified=True, active=True) -> User:
    user = User(
        email=f"u{_utcnow().timestamp()}@example.com",
        username=f"user{int(_utcnow().timestamp() * 1000)}",
        hashed_password=AuthService.hash_password("password123"),
        is_verified=verified,
        is_active=active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ── Service level ───────────────────────────────────────────────────────────

def test_issue_stores_only_hash(db):
    user = _make_user(db)
    plaintext = RefreshTokenService(db).issue(user)
    db.commit()

    row = db.query(RefreshToken).filter_by(user_id=user.id).one()
    assert row.token_hash == hash_refresh(plaintext)
    assert row.token_hash != plaintext  # plaintext never stored
    assert row.revoked_at is None
    assert row.expires_at > _utcnow()


def test_rotate_revokes_old_and_issues_successor(db):
    user = _make_user(db)
    svc = RefreshTokenService(db)
    first = svc.issue(user)
    db.commit()

    rotated_user, second = svc.rotate(first)
    db.commit()

    assert rotated_user.id == user.id
    assert second != first
    old = db.query(RefreshToken).filter_by(token_hash=hash_refresh(first)).one()
    new = db.query(RefreshToken).filter_by(token_hash=hash_refresh(second)).one()
    assert old.revoked_at is not None          # old revoked
    assert new.revoked_at is None              # new active
    assert new.family_id == old.family_id      # same family
    assert new.rotated_from == old.id
    assert new.expires_at == old.expires_at    # lifetime not extended


def test_reuse_detection_revokes_whole_family(db):
    user = _make_user(db)
    svc = RefreshTokenService(db)
    first = svc.issue(user)
    db.commit()
    _, second = svc.rotate(first)   # first is now revoked
    db.commit()

    # Replaying the already-rotated `first` token = theft signal.
    with pytest.raises(RefreshError) as exc:
        svc.rotate(first)
    db.commit()
    assert exc.value.code == "token_reused"

    # The entire family (including the still-valid `second`) is revoked.
    active = db.query(RefreshToken).filter_by(
        family_id=exc.value.family_id, revoked_at=None
    ).count()
    assert active == 0
    with pytest.raises(RefreshError) as exc2:
        svc.rotate(second)
    assert exc2.value.code == "token_reused"


def test_expired_token_rejected(db):
    user = _make_user(db)
    plaintext = RefreshTokenService(db).issue(user)
    db.query(RefreshToken).filter_by(token_hash=hash_refresh(plaintext)).update(
        {"expires_at": _utcnow() - timedelta(seconds=1)}
    )
    db.commit()

    with pytest.raises(RefreshError) as exc:
        RefreshTokenService(db).rotate(plaintext)
    assert exc.value.code == "expired"


def test_unknown_token_rejected(db):
    with pytest.raises(RefreshError) as exc:
        RefreshTokenService(db).rotate("not-a-real-token")
    assert exc.value.code == "invalid"


def test_revoke_all_for_user(db):
    user = _make_user(db)
    svc = RefreshTokenService(db)
    svc.issue(user)
    svc.issue(user)
    db.commit()
    svc.revoke_all_for_user(user)
    db.commit()

    active = db.query(RefreshToken).filter_by(user_id=user.id, revoked_at=None).count()
    assert active == 0


# ── Endpoint level ──────────────────────────────────────────────────────────

def test_login_returns_access_and_refresh(client, db):
    _make_user(db)
    # find the user we just made to log in
    user = db.query(User).order_by(User.created_at.desc()).first()
    res = client.post(
        "/v1/auth/login",
        data={"username": user.email, "password": "password123"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"


def test_refresh_endpoint_rotates(client, db):
    user = _make_user(db)
    login = client.post(
        "/v1/auth/login",
        data={"username": user.email, "password": "password123"},
    ).json()

    res = client.post("/v1/auth/refresh", json={"refresh_token": login["refresh_token"]})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["access_token"] != login["access_token"]
    assert body["refresh_token"] != login["refresh_token"]


def test_refresh_reuse_returns_401(client, db):
    user = _make_user(db)
    login = client.post(
        "/v1/auth/login",
        data={"username": user.email, "password": "password123"},
    ).json()
    old_refresh = login["refresh_token"]

    # First rotation succeeds.
    client.post("/v1/auth/refresh", json={"refresh_token": old_refresh})
    # Replaying the old token is rejected as reuse.
    res = client.post("/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "TOKEN_REUSED"


def test_invalid_refresh_returns_401(client):
    res = client.post("/v1/auth/refresh", json={"refresh_token": "garbage"})
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"
