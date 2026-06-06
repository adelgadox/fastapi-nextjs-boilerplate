"""Check Railway and Vercel operational status via their public Statuspage APIs.

Used to enrich Slack error alerts so you know immediately whether a backend
error is caused by upstream infrastructure rather than your own code.

Results are cached in-memory for 60s so a burst of errors doesn't hammer the
status APIs.
"""
import asyncio
import logging
import time
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

# Atlassian Statuspage API — standard across all providers using Statuspage
_STATUS_URLS = {
    "Railway": "https://status.railway.com/api/v2/status.json",
    "Vercel":  "https://www.vercel-status.com/api/v2/status.json",
}

# Indicator → emoji + label
_INDICATOR_MAP = {
    "none":     ("✅", "Operational"),
    "minor":    ("🟡", "Minor outage"),
    "major":    ("🔴", "Major outage"),
    "critical": ("🚨", "Critical outage"),
}

_cache: dict[str, tuple[float, "ProviderStatus"]] = {}
_CACHE_TTL = 60  # seconds


@dataclass
class ProviderStatus:
    name: str
    indicator: str        # none | minor | major | critical
    description: str
    url: str

    @property
    def is_incident(self) -> bool:
        return self.indicator != "none"

    @property
    def slack_line(self) -> str:
        emoji, label = _INDICATOR_MAP.get(self.indicator, ("❓", self.indicator))
        return f"{emoji} *{self.name}*: {label} — {self.description}"


async def _fetch_status(name: str, url: str, client: httpx.AsyncClient) -> ProviderStatus:
    try:
        resp = await client.get(url, timeout=3.0)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status", {})
        return ProviderStatus(
            name=name,
            indicator=status.get("indicator", "none"),
            description=status.get("description", "Unknown"),
            url=url.replace("/api/v2/status.json", ""),
        )
    except Exception as exc:
        logger.debug("Could not fetch %s status: %s", name, exc)
        return ProviderStatus(name=name, indicator="none", description="Status unavailable", url="")


async def get_infra_status() -> list[ProviderStatus]:
    """Return current status for Railway and Vercel, using a 60s TTL cache."""
    now = time.monotonic()
    results = []

    providers_to_fetch = []
    for name, url in _STATUS_URLS.items():
        cached_at, cached_status = _cache.get(name, (0.0, None))
        if cached_status is not None and (now - cached_at) < _CACHE_TTL:
            results.append((name, cached_status))
        else:
            providers_to_fetch.append((name, url))

    if providers_to_fetch:
        async with httpx.AsyncClient() as client:
            fetched = await asyncio.gather(
                *[_fetch_status(name, url, client) for name, url in providers_to_fetch],
                return_exceptions=True,
            )
        for (name, _), status in zip(providers_to_fetch, fetched):
            if isinstance(status, ProviderStatus):
                _cache[name] = (now, status)
                results.append((name, status))

    order = list(_STATUS_URLS.keys())
    results.sort(key=lambda x: order.index(x[0]) if x[0] in order else 99)
    return [s for _, s in results]


def build_slack_context(statuses: list[ProviderStatus]) -> str:
    """Return a Slack-formatted context block, or "" when all providers are healthy."""
    incidents = [s for s in statuses if s.is_incident]
    if not incidents:
        return ""

    lines = ["", "━━━ Infrastructure Status ━━━"]
    for s in statuses:
        lines.append(s.slack_line)
    lines.append("<https://status.railway.com|Railway status> · <https://www.vercel-status.com|Vercel status>")
    return "\n".join(lines)
