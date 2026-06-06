import logging
import sys
from contextlib import asynccontextmanager

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.config import settings
from app.utils.cloudflare import get_client_ip
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


class AdminIPAllowlistMiddleware(BaseHTTPMiddleware):
    """Block /v1/admin/* requests from IPs not in ADMIN_ALLOWED_IPS.

    Only active when ADMIN_ALLOWED_IPS is set and non-empty.
    """

    def __init__(self, app, allowed_ips: set[str]) -> None:
        super().__init__(app)
        self._allowed = allowed_ips

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self._allowed or not request.url.path.startswith("/v1/admin/"):
            return await call_next(request)

        client_ip = get_client_ip(request)
        if client_ip not in self._allowed:
            logger.warning("Admin access denied for IP %s on %s", client_ip, request.url.path)
            return Response(content="Forbidden", status_code=403)

        return await call_next(request)


class CloudflareOnlyMiddleware(BaseHTTPMiddleware):
    """Block requests that did not pass through Cloudflare.

    Only active when CLOUDFLARE_ONLY=true. The /health endpoint is always allowed.
    Detection: Cloudflare always injects CF-Connecting-IP on proxied requests.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if not settings.cloudflare_only or request.url.path == "/health":
            return await call_next(request)

        if not request.headers.get("CF-Connecting-IP"):
            client = request.client.host if request.client else "unknown"
            logger.warning("Blocked request without CF-Connecting-IP from %s", client)
            return Response(content="Forbidden", status_code=403)

        return await call_next(request)


# ── Sentry ─────────────────────────────────────────────────────────────────────

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
    )

# ── Startup guard ──────────────────────────────────────────────────────────────

if len(settings.secret_key.encode()) < 32:
    raise ValueError(
        "SECRET_KEY is too short — minimum 32 bytes required. "
        "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
    )

if settings.debug:
    logger.warning(
        "FastAPI DEBUG mode is ON — full stack traces exposed in responses. "
        "Set DEBUG=false in production."
    )

# ── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    from app import arq_pool

    await arq_pool.startup()
    try:
        yield
    finally:
        await arq_pool.shutdown()


# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
app.state.limiter = limiter


# ── Error envelope ─────────────────────────────────────────────────────────────

def _make_envelope(code: str, message: str, field: str | None = None, meta: dict | None = None) -> dict:
    return {"error": {"code": code, "message": message, "field": field, "meta": meta}}


def _envelope_from_http_exc(exc: HTTPException) -> dict:
    from app.utils.errors import default_code
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        return {"error": detail}
    if isinstance(detail, str):
        return _make_envelope(default_code(exc.status_code), detail)
    return _make_envelope(default_code(exc.status_code), str(detail))


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=_envelope_from_http_exc(exc))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(loc) for loc in first.get("loc", [])[1:]) or None
    message = first.get("msg", "Validation error")
    return JSONResponse(
        status_code=422,
        content=_make_envelope("VALIDATION_ERROR", message, field=field),
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content=_make_envelope("RATE_LIMIT_EXCEEDED", f"Rate limit exceeded: {exc.detail}"),
    )


async def _alert_500(path: str, exc: Exception) -> None:
    """Send a Slack 500 alert enriched with Railway/Vercel infra status."""
    from app.utils.slack import notify_slack
    from app.utils.infra_status import get_infra_status, build_slack_context

    context = ""
    try:
        context = build_slack_context(await get_infra_status())
    except Exception:
        pass  # Never let alert enrichment swallow the original error path

    await notify_slack(
        f":rotating_light: *Backend 500* — `{path}`\n"
        f"```{type(exc).__name__}: {exc}```" + context,
        channel="#backend-alerts",
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    import asyncio

    path = f"{request.method} {request.url.path}"
    logger.error("Unhandled exception on %s", path, exc_info=exc)

    if settings.sentry_dsn:
        sentry_sdk.capture_exception(exc)

    asyncio.create_task(_alert_500(path, exc))

    return JSONResponse(
        status_code=500,
        content=_make_envelope("INTERNAL_ERROR", "Internal server error"),
    )


# ── Middleware stack (applied in reverse order) ────────────────────────────────

_admin_allowed_ips = {ip.strip() for ip in settings.admin_allowed_ips.split(",") if ip.strip()}

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(AdminIPAllowlistMiddleware, allowed_ips=_admin_allowed_ips)
app.add_middleware(CloudflareOnlyMiddleware)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=settings.trusted_proxy_ips)

_allowed_origins = [o.strip().rstrip("/") for o in settings.frontend_url.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# ── Versioned routers ──────────────────────────────────────────────────────────

_V1 = "/v1"

app.include_router(auth.router, prefix=_V1)


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}
