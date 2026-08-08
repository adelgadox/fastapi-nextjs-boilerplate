"""
Cloudflare integration utilities.

- get_client_ip: reads the real visitor IP from CF-Connecting-IP (set by
  Cloudflare on every proxied request), falling back to X-Forwarded-For and
  then request.client.host for local/non-proxied environments.

Note: there is deliberately NO Cloudflare CIDR validation here. Verifying that
the TCP peer belongs to Cloudflare's published IP ranges only works when
Cloudflare connects directly to the origin. On platforms with an internal proxy
between Cloudflare and the app (e.g. Railway), the raw peer is the platform's
proxy — never a Cloudflare edge IP — so a CIDR check blocks 100% of traffic.
Origin protection is enforced instead by CloudflareOnlyMiddleware in app.main,
which validates the X-Origin-Auth shared secret injected by a Cloudflare
Transform Rule.
"""

from fastapi import Request


def get_client_ip(request: Request) -> str:
    """Return the real visitor IP address.

    Priority:
    1. CF-Connecting-IP  — set by Cloudflare, cannot be spoofed when proxied
    2. X-Forwarded-For   — first entry (original client), set by most proxies
    3. request.client.host — direct connection (local dev / non-proxied)
    """
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()

    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    if request.client:
        return request.client.host

    return "unknown"
