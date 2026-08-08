"""Rate-limit coverage over the registered routes.

The project convention (CLAUDE.md) requires `@limiter.limit()` on every public
or authenticated endpoint. A convention that only lives in a document breaks
without anyone noticing. This test walks the application's real routes and
fails when one appears without a limit and without a declared exemption. The
list exists so an exemption is a written decision, not an oversight.
"""

from app.main import app
from app.utils.rate_limit import limiter

# Routes that are deliberately unlimited. Every entry needs its reason.
EXEMPT = {
    # The platform hits /health to decide whether the container is alive: a
    # limit that blocks it turns a traffic spike into a restart loop. It can
    # afford this because it returns a constant — no database, no Redis.
    "health",
    # GET /verify-email is a one-click link from an email; the token itself is
    # single-use and unguessable. TODO: consider a generous limit anyway.
    "verify_email",
}

# Routes FastAPI registers on its own that are not project endpoints.
_FRAMEWORK = {"swagger_ui_html", "openapi", "redoc_html", "swagger_ui_redirect"}


def _limited_endpoints() -> set[str]:
    """Function names slowapi has marked as limited.

    NOTE: reads slowapi's private `_Limiter__marked_for_limiting` — version-
    sensitive by nature; the meta-tests below catch a silent breakage.
    """
    marked = getattr(limiter, "_Limiter__marked_for_limiting")
    return {qualified.rsplit(".", 1)[-1] for qualified in marked}


def _walk(routes):
    """Walk the real routes, including those behind an included router.

    Some FastAPI versions do NOT flatten `include_router` into `app.routes`:
    they leave one wrapper per include and the true routes live inside, in
    `original_router`. A naive walk sees a couple of routes and green-lights
    an application with dozens unchecked.
    """
    for route in routes:
        included = getattr(route, "original_router", None)
        if included is not None:
            yield from _walk(included.routes)
            continue
        if getattr(route, "endpoint", None) is not None:
            yield route


def _project_routes():
    for route in _walk(app.routes):
        name = route.endpoint.__name__
        if name in _FRAMEWORK:
            continue
        if not getattr(route.endpoint, "__module__", "").startswith("app."):
            continue
        yield route, name


def test_every_route_is_rate_limited_or_explicitly_exempt():
    limited = _limited_endpoints()

    unlimited = sorted(
        f"{sorted(route.methods or [])} {route.path} ({name})"
        for route, name in _project_routes()
        if name not in limited and name not in EXEMPT
    )

    assert not unlimited, (
        "These routes have no rate limit and no declared exemption:\n  "
        + "\n  ".join(unlimited)
    )


def test_the_exemption_list_stays_short():
    """A growing exemption list is the convention dying slowly."""
    assert len(EXEMPT) <= 3


def test_exempt_routes_still_exist():
    """An exemption for a deleted route hides the next one that gets added."""
    names = {name for _, name in _project_routes()}
    assert EXEMPT <= names


def test_the_public_job_health_endpoint_is_limited():
    """It's public and queries the database on every visit: unlimited, it's an open tap."""
    assert "health_jobs" in _limited_endpoints()


def test_the_walk_reaches_the_routes_behind_included_routers():
    """Guard for the walk itself.

    If FastAPI's routing internals change and the walk stops seeing the routes
    behind `include_router`, this count exposes it instead of the coverage
    test silently passing on an empty set.
    """
    assert len(list(_project_routes())) >= 10
