"""Generic Redis cache with graceful degradation.

Every function is a no-op (returns the miss/None path) when ``REDIS_URL`` is
unset or Redis is unreachable, so callers never need to branch on availability —
they simply fall back to the source of truth (DB, external API, recompute).

The client is created lazily on first use and a single failed connection flips
``_unavailable`` so we never retry-storm a down Redis on a hot path.

Example::

    from app.utils import cache

    cached = cache.get(f"profile:{user_id}")
    if cached is None:
        cached = serialize(load_profile(user_id))
        cache.set(f"profile:{user_id}", cached, ttl=300)
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

_client = None
_unavailable = False  # once Redis is confirmed down, skip further attempts


def get_redis_client():
    """Return the shared Redis client, or None when Redis is unavailable.

    Also used by ARQ / rate limiting layers that need the raw client.
    """
    global _client, _unavailable
    if _unavailable:
        return None
    if _client is not None:
        return _client

    from app.config import settings

    url = settings.redis_url
    if not url:
        _unavailable = True
        return None
    try:
        import redis as redis_lib

        _client = redis_lib.from_url(url, decode_responses=True, socket_timeout=0.5)
        _client.ping()
        logger.info("Redis cache connected")
    except Exception:
        logger.warning("Redis unavailable — cache disabled")
        _client = None
        _unavailable = True
    return _client


def get(key: str) -> Optional[str]:
    """Return the cached string value for *key*, or None on miss/error."""
    r = get_redis_client()
    if r is None:
        return None
    try:
        return r.get(key)
    except Exception:
        logger.debug("Redis GET failed for key=%s", key)
        return None


def set(key: str, value: str, ttl: int = 300) -> None:
    """Cache *value* under *key* for *ttl* seconds."""
    r = get_redis_client()
    if r is None:
        return
    try:
        r.setex(key, ttl, value)
    except Exception:
        logger.debug("Redis SETEX failed for key=%s", key)


def delete(key: str) -> None:
    """Invalidate *key* (call on write/update/delete of the cached entity)."""
    r = get_redis_client()
    if r is None:
        return
    try:
        r.delete(key)
    except Exception:
        logger.debug("Redis DEL failed for key=%s", key)


def incr(key: str) -> Optional[int]:
    """Atomically increment a counter at *key*.

    Returns the new value, or None when Redis is unavailable (caller should
    then persist directly to the source of truth).
    """
    r = get_redis_client()
    if r is None:
        return None
    try:
        return r.incr(key)
    except Exception:
        logger.debug("Redis INCR failed for key=%s", key)
        return None
