"""Minimum supported native-client version.

The web deploys alongside the backend, so an incompatible change is
coordinated in one PR. An installed app is not: it may be running a
months-old binary, and on a bad connection nobody updates it. This endpoint
gives the app a place to ask "am I still supported?" and show "update to
continue" instead of silently breaking against a changed contract.

Public and edge-cacheable: no database, no per-user data, no session needed.
Values live in the environment (set by whoever operates the deploy when an
app version ships), not in this repository.
"""

from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.config import settings
from app.schemas.client import ClientVersionOut
from app.utils.rate_limit import limiter

router = APIRouter(tags=["client"])

_PUBLIC_CACHE = "public, max-age=300, s-maxage=3600, stale-while-revalidate=86400"


@router.get("/client/version", response_model=ClientVersionOut)
@limiter.limit("60/minute")
def client_version(request: Request):
    payload = ClientVersionOut(
        min_supported=settings.min_supported_client_version,
        latest=settings.latest_client_version,
    )
    return Response(
        content=payload.model_dump_json(),
        media_type="application/json",
        headers={"Cache-Control": _PUBLIC_CACHE},
    )
