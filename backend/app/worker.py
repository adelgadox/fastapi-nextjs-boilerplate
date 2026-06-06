"""ARQ worker task definitions and settings.

Each task is an async function receiving (ctx, *args, **kwargs); ``ctx`` is the
dict ARQ provides (pool, job_id, job_try, ...).

FALLBACKS maps each task name to the plain callable used when Redis is down and
the work runs in-process via FastAPI BackgroundTasks instead (see arq_pool.py).

Run the worker:
    cd backend && arq app.worker.WorkerSettings

To add a task:
    1. Write an async ``<name>_task(ctx, ...)`` here that does the work.
    2. Register it in WorkerSettings.functions.
    3. Map its name → the underlying callable in _build_fallbacks().
    4. Enqueue it from a service with:
           from app.arq_pool import enqueue
           enqueue(background_tasks, "<name>_task", *args)
"""

import asyncio
import logging
import os

from arq.connections import RedisSettings

logger = logging.getLogger(__name__)


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


# ── Example cron (uncomment to enable a scheduled job) ─────────────────────────
#
# from arq.cron import cron
#
# async def daily_cleanup_cron(ctx) -> None:
#     """Runs daily at 3 AM UTC."""
#     from app.database import SessionLocal
#     with SessionLocal() as db:
#         ...  # purge expired tokens, send digests, etc.
#
# Then add to WorkerSettings.cron_jobs:
#     cron(daily_cleanup_cron, hour=3, minute=0)


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
    functions = [
        notify_slack_task,
        send_verification_email_task,
        send_password_reset_email_task,
    ]
    cron_jobs: list = []
    redis_settings = RedisSettings.from_dsn(os.environ.get("REDIS_URL", "redis://localhost:6379"))
    max_jobs = 10
    job_timeout = 60
    keep_result = 3600
    retry_jobs = True
    max_tries = 3
