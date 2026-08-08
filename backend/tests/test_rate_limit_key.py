"""The rate-limit key separates by user, not only by IP.

IP-only keying breaks with mobile CGNAT (several people share one IPv4) and
with Next.js server-side calls (all requests exit through the same egress IP).
With a valid token the key is the token's user; otherwise the IP. The signature
is verified so nobody can forge a `sub` to escape their bucket.
"""

from types import SimpleNamespace

import jwt

from app.config import settings
from app.utils.rate_limit import rate_limit_key


def _request(headers: dict | None = None, ip: str = "203.0.113.7"):
    return SimpleNamespace(
        headers=SimpleNamespace(get=(headers or {}).get),
        client=SimpleNamespace(host=ip),
    )


def _token(sub: str, secret: str | None = None) -> str:
    return jwt.encode(
        {"sub": sub}, secret or settings.secret_key, algorithm=settings.algorithm
    )


def test_a_valid_token_keys_by_user():
    req = _request({"Authorization": f"Bearer {_token('user-123')}"})
    assert rate_limit_key(req) == "user:user-123"


def test_two_users_behind_one_ip_get_separate_keys():
    # The CGNAT case: same IP, different person, different bucket.
    a = _request({"Authorization": f"Bearer {_token('aaa')}"}, ip="198.51.100.1")
    b = _request({"Authorization": f"Bearer {_token('bbb')}"}, ip="198.51.100.1")
    assert rate_limit_key(a) != rate_limit_key(b)


def test_no_token_keys_by_ip():
    req = _request({}, ip="203.0.113.9")
    assert rate_limit_key(req) == "ip:203.0.113.9"


def test_cf_connecting_ip_wins_for_anonymous():
    req = _request({"CF-Connecting-IP": "203.0.113.50"}, ip="10.0.0.1")
    assert rate_limit_key(req) == "ip:203.0.113.50"


def test_a_forged_signature_falls_back_to_ip():
    # Signed with a different secret: its `sub` can't be trusted, so it gets
    # limited by IP instead of a self-invented private bucket.
    forged = _token("attacker", secret="a-different-secret-not-ours-at-all-32ch")
    req = _request({"Authorization": f"Bearer {forged}"}, ip="203.0.113.11")
    assert rate_limit_key(req) == "ip:203.0.113.11"


def test_garbage_bearer_falls_back_to_ip():
    req = _request({"Authorization": "Bearer not-a-jwt"}, ip="203.0.113.12")
    assert rate_limit_key(req) == "ip:203.0.113.12"
