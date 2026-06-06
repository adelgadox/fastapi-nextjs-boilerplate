"""Symmetric encryption for sensitive DB-stored values (e.g. third-party API keys).

Uses Fernet (AES-128-CBC + HMAC-SHA256). The key is derived from a dedicated
``ENCRYPTION_KEY`` env var when set, otherwise it falls back to ``SECRET_KEY``
so the feature works out of the box. A dedicated ``ENCRYPTION_KEY`` is preferred
in production for key separation (rotating JWT signing keys should not silently
invalidate encrypted columns).

Usage::

    from app.utils.crypto import encrypt_value, decrypt_value

    ciphertext = encrypt_value("sk-abc123")
    plaintext  = decrypt_value(ciphertext)   # "sk-abc123"
"""

import base64
import hashlib

from cryptography.fernet import Fernet


def _get_fernet() -> Fernet:
    """Lazily build a Fernet instance from config."""
    from app.config import settings  # local import to avoid circular deps

    raw = getattr(settings, "encryption_key", "") or settings.secret_key
    # Fernet requires exactly 32 URL-safe base64-encoded bytes.
    # Derive a stable 32-byte key from whatever string we have.
    key_bytes = hashlib.sha256(raw.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(fernet_key)


def encrypt_value(plaintext: str) -> str:
    """Encrypt *plaintext* and return a URL-safe base64 ciphertext string."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a ciphertext produced by :func:`encrypt_value`."""
    return _get_fernet().decrypt(ciphertext.encode()).decode()
