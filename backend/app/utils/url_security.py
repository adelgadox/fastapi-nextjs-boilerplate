"""
Server-Side Request Forgery (SSRF) protection for user-supplied URLs.

Use this before storing or fetching any URL that came from a user (link
shorteners, webhooks, avatar imports, embeds, etc.):

    Layer 1 — validate_url(): scheme/host/IP checks, blocks internal targets.
    Layer 2 — check_safe_browsing(): optional Google Safe Browsing reputation.

Both layers fail safe in different directions:
  - validate_url() is strict (rejects on any doubt).
  - check_safe_browsing() fails open (never blocks a user if the API is down).
"""
import ipaddress
from urllib.parse import urlparse

import httpx

_ALLOWED_SCHEMES = {"https"}

_BLOCKED_HOSTS = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "broadcasthost",
}

_THREAT_MESSAGES = {
    "MALWARE": "This URL has been flagged as malware.",
    "SOCIAL_ENGINEERING": "This URL has been flagged as a phishing or social engineering site.",
    "UNWANTED_SOFTWARE": "This URL has been flagged as unwanted software.",
    "POTENTIALLY_HARMFUL_APPLICATION": "This URL has been flagged as potentially harmful.",
}


def validate_url(url: str) -> str | None:
    """
    Layer 1 — basic URL validation against SSRF.
    Returns an error message string if the URL is invalid/blocked, or None if it's safe.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return "Invalid URL."

    if parsed.scheme not in _ALLOWED_SCHEMES:
        return "Only https:// URLs are accepted."

    hostname = (parsed.hostname or "").lower()

    if not hostname:
        return "Invalid URL: missing host."

    if hostname in _BLOCKED_HOSTS:
        return "This URL is not allowed."

    # Block private / loopback / reserved IP addresses
    try:
        ip = ipaddress.ip_address(hostname)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_reserved
            or ip.is_link_local
            or ip.is_multicast
        ):
            return "This URL is not allowed."
    except ValueError:
        pass  # Not an IP address — fine

    # Block hostnames that try to resolve to internal infrastructure
    internal_suffixes = (".local", ".internal", ".localhost", ".corp", ".lan")
    if any(hostname.endswith(s) for s in internal_suffixes):
        return "This URL is not allowed."

    return None


async def check_safe_browsing(url: str, api_key: str) -> str | None:
    """
    Layer 2 — Google Safe Browsing API v4 reputation check.
    Returns an error message if the URL is flagged, or None if it's safe.
    Silently passes (fail open) if the API key is not set or the request fails.
    """
    if not api_key:
        return None

    from app.config import settings

    payload = {
        "client": {"clientId": settings.app_name, "clientVersion": "1.0"},
        "threatInfo": {
            "threatTypes": [
                "MALWARE",
                "SOCIAL_ENGINEERING",
                "UNWANTED_SOFTWARE",
                "POTENTIALLY_HARMFUL_APPLICATION",
            ],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}],
        },
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(
                f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={api_key}",
                json=payload,
            )
            if r.status_code == 200:
                matches = r.json().get("matches", [])
                if matches:
                    threat_type = matches[0].get("threatType", "THREAT")
                    return _THREAT_MESSAGES.get(threat_type, "This URL has been flagged as unsafe.")
    except Exception:
        pass  # Fail open — don't block users if the API is unreachable

    return None
