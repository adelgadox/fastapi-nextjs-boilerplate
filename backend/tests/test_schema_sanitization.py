"""Input sanitization is wired into the auth schemas, not just available.

Defence-in-depth at the boundary: SQLAlchemy already parameterizes and React
already escapes, but keeping garbage out of the database means every future
consumer (emails, exports, a Flutter app rendering raw strings) inherits clean
data.
"""

import pytest
from pydantic import ValidationError

from app.schemas.auth import OAuthLogin, UserCreate


def _user(**overrides) -> dict:
    base = {
        "email": "person@example.com",
        "username": "person",
        "password": "long-enough-password",
    }
    return {**base, **overrides}


def test_email_is_normalized():
    u = UserCreate(**_user(email="  Person@Example.COM "))
    assert u.email == "person@example.com"


def test_a_garbage_email_is_rejected():
    with pytest.raises(ValidationError):
        UserCreate(**_user(email="not-an-email"))


def test_username_rules_are_enforced():
    with pytest.raises(ValidationError):
        UserCreate(**_user(username="<script>"))


def test_a_short_password_is_rejected_at_the_schema():
    with pytest.raises(ValidationError):
        UserCreate(**_user(password="short"))


def test_full_name_html_is_stripped():
    u = UserCreate(**_user(full_name="<b>Ana</b> <script>x</script>López"))
    assert "<" not in u.full_name
    assert "Ana" in u.full_name


def test_unknown_fields_are_rejected():
    # extra="forbid": a client sending {"role": "admin"} gets a 422, the field
    # is never silently dropped or honored.
    with pytest.raises(ValidationError):
        UserCreate(**_user(role="admin"))


def test_oauth_avatar_dangerous_scheme_is_rejected():
    with pytest.raises(ValidationError):
        OAuthLogin(email="p@example.com", avatar_url="javascript:alert(1)")
