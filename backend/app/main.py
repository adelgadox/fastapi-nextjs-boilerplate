import logging
import sys

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.config import settings
from app.utils.cloudflare import get_client_ip  # noqa: F401 — used by rate limiter
from app.utils.rate_limit import limiter

# ── Routers ────────────────────────────────────────────────────────────────────
from app.routers import auth

# ── Models (ensure tables are registered with SQLAlchemy) ─────────────────────
from app.models import user as _user_model          # noqa: F401
from app.models import token_denylist as _token_denylist_model  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


# ── Middleware ─────────────────────────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response


# ── Sentry ─────────────────────────────────────────────────────────────────────

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
    )

# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(title=settings.app_name, debug=settings.debug)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    import asyncio
    from app.utils.slack import notify_slack

    path = f"{request.method} {request.url.path}"
    logger.error("Unhandled exception on %s", path, exc_info=exc)

    if settings.sentry_dsn:
        sentry_sdk.capture_exception(exc)

    asyncio.create_task(
        notify_slack(
            f":rotating_light: *Backend 500* — `{path}`\n"
            f"```{type(exc).__name__}: {exc}```",
            channel="#backend-alerts",
        )
    )

    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=settings.trusted_proxy_ips)

_allowed_origins = [o.strip().rstrip("/") for o in settings.frontend_url.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(auth.router)


@app.get("/health")
def health():
    return {"status": "ok"}
