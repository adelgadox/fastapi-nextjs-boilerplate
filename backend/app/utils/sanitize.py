"""
Input sanitization helpers for use in Pydantic schema validators.

Note on SQL injection: SQLAlchemy ORM uses parameterized queries everywhere,
so SQL injection is already prevented at the data-access layer. These helpers
add defence-in-depth at the schema layer.

Note on XSS: React/Next.js auto-escapes JSX content, so stored HTML would
never be executed. Still, keeping raw HTML out of the database is good practice.

Usage (inside a StrictModel schema)::

    from pydantic import field_validator
    from app.utils.sanitize import strip_html, validate_username

    class CreateUser(StrictModel):
        username: str
        bio: str

        _username = field_validator("username")(staticmethod(validate_username))

        @field_validator("bio")
        @classmethod
        def _clean_bio(cls, v: str) -> str:
            return strip_html(v)
"""
import html
import re
from urllib.parse import urlparse

# Matches any HTML / XML tag
_TAG_RE = re.compile(r"<[^>]+>", re.DOTALL)

# Valid username: lowercase letters/digits/underscore/hyphen, must start alphanumeric
_USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

# Valid slug: lowercase letters, digits, hyphens only
_SLUG_RE = re.compile(r"^[a-z0-9-]+$")

# URL schemes that must never reach the database
_DANGEROUS_SCHEMES = {"javascript", "data", "vbscript", "file"}


def strip_html(value: str) -> str:
    """Remove all HTML/XML tags and decode HTML entities, then strip whitespace."""
    cleaned = _TAG_RE.sub("", value)
    return html.unescape(cleaned).strip()


def validate_username(value: str) -> str:
    value = value.strip().lower()
    if len(value) < 3:
        raise ValueError("Username must be at least 3 characters long.")
    if len(value) > 30:
        raise ValueError("Username must be at most 30 characters long.")
    if not _USERNAME_RE.match(value):
        raise ValueError(
            "Username may only contain lowercase letters, numbers, underscores, and hyphens, "
            "and must start with a letter or number."
        )
    return value


def validate_slug(value: str) -> str:
    value = value.strip().lower()
    if len(value) < 3:
        raise ValueError("Slug must be at least 3 characters long.")
    if len(value) > 60:
        raise ValueError("Slug must be at most 60 characters long.")
    if not _SLUG_RE.match(value):
        raise ValueError("Slug may only contain lowercase letters, numbers, and hyphens.")
    return value


def validate_url_scheme(value: str) -> str:
    """Block obviously dangerous URL schemes (javascript:, data:, etc.)."""
    try:
        scheme = urlparse(value.strip()).scheme.lower()
    except Exception:
        raise ValueError("Invalid URL.")
    if scheme in _DANGEROUS_SCHEMES:
        raise ValueError(f"URLs with the '{scheme}:' scheme are not allowed.")
    return value
