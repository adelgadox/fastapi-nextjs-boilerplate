"""ARQ (async Redis queue) pool management.

Jobs enqueued here are stored durably in Redis before the HTTP response is sent.
A separate ARQ worker process picks them up and executes them, surviving server
restarts and retrying on failure.

When Redis is unavailable the pool is None and enqueue() falls back to running
the task directly via FastAPI BackgroundTasks — so no task is ever silently
dropped and the app keeps working with zero Redis dependency in local dev.

Run the worker:
    cd backend && arq app.worker.WorkerSettings
"""

import logging

from fastapi import BackgroundTasks

logger = logging.getLogger(__name__)

_pool = None


async def startup() -> None:
    """Create the ARQ Redis pool. Called from the FastAPI lifespan startup."""
    global _pool
    from app.config import settings

    if not settings.redis_url:
        logger.info("REDIS_URL not set — ARQ disabled; tasks run in-process via BackgroundTasks")
        return
    try:
        from arq import create_pool
        from arq.connections import RedisSettings

        _pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        logger.info("ARQ pool connected")
    except Exception as exc:
        logger.warning("ARQ pool unavailable (%s) — tasks will run in-process", exc)
        _pool = None


async def shutdown() -> None:
    """Close the ARQ pool on shutdown."""
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None
        logger.info("ARQ pool closed")


def get_pool():
    """Return the active ArqRedis pool, or None if unavailable."""
    return _pool


def enqueue(background_tasks: BackgroundTasks, task_name: str, *args, **kwargs) -> None:
    """Enqueue a durable background task.

    With ARQ (Redis available): stores the job in Redis; the worker process
    executes it independently of this server process.

    Without ARQ (Redis down or unset): schedules the registered fallback
    function directly via FastAPI BackgroundTasks so nothing is dropped.
    """
    pool = _pool
    if pool is not None:
        background_tasks.add_task(pool.enqueue_job, task_name, *args, **kwargs)
        return

    from app.worker import FALLBACKS

    fn = FALLBACKS.get(task_name)
    if fn is not None:
        background_tasks.add_task(fn, *args, **kwargs)
    else:
        logger.warning("ARQ: no fallback registered for task %r — task dropped", task_name)
