"""Rate limiting: keyed by user when authenticated, by IP otherwise.

IP-only keying breaks in two scenarios this stack actually has:

- **Mobile CGNAT.** Several users of the same carrier share one public IPv4.
  With an IP key, one user's traffic exhausts everyone else's quota. This is
  the case that matters most for a future native (Flutter) app, where traffic
  arrives through Cloudflare with the client's real IP.
- **Next.js route handlers / server actions.** They call the backend from the
  Vercel server, so all those requests share Vercel's egress IP; with an IP key
  they all fall into the same bucket. Since they forward the user's
  `Authorization` header, keying by `sub` separates them correctly.

When the request carries a valid token we limit by the token's user; anonymous
routes (login, public) stay keyed by IP, which is where that makes sense. The
token signature IS verified: without that, a client could forge a `sub` to
spread its load across many buckets and evade the limit.

The counter lives in Redis when available (`redis_url`) so it survives deploys
and is shared across replicas; without Redis it falls back to process memory.
If Redis is configured but unreachable, `in_memory_fallback_enabled` lets the
process keep limiting in memory instead of failing every request: fail open
toward the service.
"""

import jwt
from slowapi import Limiter

from app.config import settings
from app.utils.cloudflare import get_client_ip


def rate_limit_key(request) -> str:
    """Rate limit key: `user:<sub>` with a valid token, `ip:<ip>` otherwise."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[len("Bearer "):].strip()
        try:
            payload = jwt.decode(
                token, settings.secret_key, algorithms=[settings.algorithm]
            )
            sub = payload.get("sub")
            if sub:
                return f"user:{sub}"
        except jwt.PyJWTError:
            # Expired, badly signed, or garbage token: limit by IP, don't fail.
            pass
    return f"ip:{get_client_ip(request)}"


limiter = Limiter(
    key_func=rate_limit_key,
    storage_uri=settings.redis_url or "memory://",
    in_memory_fallback_enabled=True,
)
