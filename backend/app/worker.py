"""ARQ worker task definitions and settings.

Each task is an async function receiving (ctx, *args, **kwargs); ``ctx`` is the
dict ARQ provides (pool, job_id, job_try, ...).

FALLBACKS maps each task name to the plain callable used when Redis is down and
the work runs in-process via FastAPI BackgroundTasks instead (see arq_pool.py).

Run the worker:
    cd backend && arq app.worker.WorkerSettings

To add a task:
    1. Write an async ``<name>_task(ctx, ...)`` here that does the work.
    2. Register it in WorkerSettings.functions wrapped in alert_on_final_failure.
    3. Map its name → the underlying callable in _build_fallbacks().
    4. Enqueue it from a service with:
           from app.arq_pool import enqueue
           enqueue(background_tasks, "<name>_task", *args)

To add a cron:
    1. Write ``<name>_cron(ctx)`` decorated with @alert_on_cron_failure.
    2. Add cron(<name>_cron, ...) to WorkerSettings.cron_jobs.
    3. Add its window to app.services.cron_heartbeat.CRON_MAX_AGE and its
       human consequence to _CRON_PROMISES below.
"""

import asyncio
import functools
import logging
import os

from arq.connections import RedisSettings
from arq.cron import cron

from app.config import settings

logger = logging.getLogger(__name__)

# The worker runs in its own process: without this, its exceptions reach no
# dashboard and only exist in the platform log. Without a DSN nothing happens.
if settings.sentry_dsn:
    import sentry_sdk

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        traces_sample_rate=0.1,
    )


# ── Failure alerts ─────────────────────────────────────────────────────────────
#
# The 500 handler covers what blows up with someone in front of it. This covers
# the rest: background work, which runs in the small hours with nobody watching.

MAX_TRIES = 3


def alert_on_final_failure(fn):
    """Alert Slack when an ARQ task **gives up**, then re-raise.

    Alerting only on the last attempt is deliberate. ARQ retries three times;
    alerting on every failure would triple the noise of a network timeout or a
    mid-deploy blip that resolves itself on the second try. What deserves an
    alert is what was left undone.

    The exception is always re-raised: the alert observes, it does not
    interfere with ARQ's retry-and-abandon logic.
    """

    @functools.wraps(fn)
    async def wrapper(ctx: dict, *args, **kwargs):
        try:
            return await fn(ctx, *args, **kwargs)
        except Exception as exc:
            # An incomplete ctx must not turn every failure into an alert.
            if (ctx or {}).get("job_try", 1) >= MAX_TRIES:
                await _alert(
                    f":rotating_light: *Background task failed* — `{fn.__name__}`\n"
                    f"All {MAX_TRIES} attempts exhausted; the work was left undone.\n"
                    f"```{type(exc).__name__}: {str(exc)[:300]}```",
                    budget_key=f"job:{fn.__name__}:{type(exc).__name__}",
                )
            raise

    return wrapper


# What each cron promises. The alert says what broke, not which exception came
# out: "TimeoutError in purge_expired_tokens_cron" serves whoever wrote the
# cron; this serves whoever reads it at three in the morning.
_CRON_PROMISES = {
    "purge_expired_tokens_cron":
        "Expired refresh tokens and denylisted access tokens stop being purged "
        "and their tables grow without bound. No security risk (expired tokens "
        "are rejected anyway), but the tables bloat.",
    "heartbeat_watchdog_cron":
        "Nobody is checking that the other crons keep running.",
}


def alert_on_cron_failure(fn):
    """A failing cron is not retried: alert and move on.

    Retrying a purge could run it twice, and some are not idempotent in their
    effect on storage. Propagating would also leave the failure with no
    recipient — nobody is watching at five in the morning.
    """

    @functools.wraps(fn)
    async def wrapper(ctx: dict, *args, **kwargs):
        try:
            result = await fn(ctx, *args, **kwargs)
        except Exception as exc:
            consequence = _CRON_PROMISES.get(fn.__name__, "")
            logger.error("%s failed: %s", fn.__name__, exc)
            await _alert(
                f":rotating_light: *A cron did not run* — `{fn.__name__}`\n"
                + (f"{consequence}\n" if consequence else "")
                + f"```{type(exc).__name__}: {str(exc)[:300]}```",
                budget_key=f"cron:{fn.__name__}:{type(exc).__name__}",
            )
            return None

        # The heartbeat is recorded at the end, and only on success: a cron
        # that failed did not run, no matter that it executed.
        await asyncio.to_thread(_record_heartbeat, fn.__name__)
        return result

    return wrapper


def _record_heartbeat(name: str) -> None:
    from app.database import SessionLocal
    from app.services.cron_heartbeat import record_success

    with SessionLocal() as db:
        record_success(db, name)


async def _alert(message: str, budget_key: str | None = None) -> None:
    """Send the alert without a broken Slack swallowing the original error.

    With `budget_key`, a repetition of the same problem inside its window is
    silenced. Without a key the alert always goes out: whatever doesn't declare
    a problem identity can't be grouped.
    """
    if budget_key is not None:
        from app.utils.alert_budget import should_send

        if not await asyncio.to_thread(should_send, budget_key):
            logger.info("Alert grouped by noise budget: %s", budget_key)
            return

    try:
        from app.utils.slack import notify_slack

        await notify_slack(message, settings.slack_alert_channel)
    except Exception:
        logger.exception("Could not post the alert to Slack")


# ── Task definitions ───────────────────────────────────────────────────────────

async def notify_slack_task(ctx, text: str, channel: str) -> None:
    from app.utils.slack import notify_slack
    await notify_slack(text, channel)


async def send_verification_email_task(ctx, to: str, token: str) -> None:
    from app.email import send_verification_email
    await asyncio.to_thread(send_verification_email, to, token)


async def send_password_reset_email_task(ctx, to: str, token: str) -> None:
    from app.email import send_password_reset_email
    await asyncio.to_thread(send_password_reset_email, to, token)


# ── Crons ──────────────────────────────────────────────────────────────────────

@alert_on_cron_failure
async def purge_expired_tokens_cron(ctx) -> None:
    """Daily purge of expired refresh tokens and expired denylist entries."""
    from app.database import SessionLocal
    from app.repositories.refresh_token_repository import RefreshTokenRepository
    from app.repositories.token_denylist_repository import TokenDenylistRepository

    with SessionLocal() as db:
        refresh_deleted = RefreshTokenRepository(db).delete_expired()
        denylist_deleted = TokenDenylistRepository(db).delete_expired()
    logger.info(
        "Token purge: %d expired refresh tokens, %d expired denylist entries",
        refresh_deleted,
        denylist_deleted,
    )


@alert_on_cron_failure
async def heartbeat_watchdog_cron(ctx) -> None:
    """Check that no cron has fallen behind.

    **A watchdog cannot detect its own death.** If the whole worker stops
    starting, this cron dies with the rest and nothing alerts — which is why
    the heartbeat is also exposed at `/health/jobs`, so the question can be
    asked from outside the process that might be dead.
    """
    from app.database import SessionLocal
    from app.services.cron_heartbeat import stale_crons

    with SessionLocal() as db:
        stale = await asyncio.to_thread(stale_crons, db)

    if stale:
        await _alert(
            ":rotating_light: *Background work has stopped running*\n"
            + "\n".join(
                f"· `{name}` — {_CRON_PROMISES.get(name, 'not running')}"
                for name in stale
            ),
            budget_key=f"heartbeat:{','.join(stale)}",
        )


# ── Fallbacks (called directly when Redis is unavailable) ──────────────────────
# These are the underlying callables, invoked WITHOUT the ARQ ctx argument.

def _build_fallbacks() -> dict:
    from app.utils.slack import notify_slack
    from app.email import send_verification_email, send_password_reset_email

    return {
        "notify_slack_task": notify_slack,
        "send_verification_email_task": send_verification_email,
        "send_password_reset_email_task": send_password_reset_email,
    }


_fallbacks_cache: dict | None = None


class _LazyFallbacks:
    """Builds the fallback registry on first access to avoid import-time side effects."""

    def get(self, key: str, default=None):
        global _fallbacks_cache
        if _fallbacks_cache is None:
            _fallbacks_cache = _build_fallbacks()
        return _fallbacks_cache.get(key, default)


FALLBACKS = _LazyFallbacks()


# ── Worker settings ────────────────────────────────────────────────────────────

class WorkerSettings:
    # Each task is wrapped here and not at its definition: a single place that
    # guarantees none goes without an alert, and the list is exactly what
    # someone edits when adding a new task.
    functions = [
        alert_on_final_failure(notify_slack_task),
        alert_on_final_failure(send_verification_email_task),
        alert_on_final_failure(send_password_reset_email_task),
    ]
    cron_jobs = [
        cron(purge_expired_tokens_cron, hour=5, minute=30),
        # Hourly: detects a cron that fell behind. What it can NOT detect is
        # its own absence — that's what /health/jobs is for.
        cron(heartbeat_watchdog_cron, minute=45),
    ]
    redis_settings = RedisSettings.from_dsn(os.environ.get("REDIS_URL", "redis://localhost:6379"))
    max_jobs = 10
    job_timeout = 60
    keep_result = 3600
    retry_jobs = True
    max_tries = MAX_TRIES
