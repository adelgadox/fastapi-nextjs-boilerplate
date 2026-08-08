"""Noise budget for alerts.

An alert is worth what it triggers. A channel where the same message shows up
forty times in a row triggers nothing: it trains the reader to ignore it, and
the day the alert that mattered appears, nobody is looking.

This module groups the repetitive. The first occurrence of a problem goes out
in full; repetitions inside its window stay silent. Grouping is not by alert
type or severity but by **problem identity**: same endpoint and same exception,
or same cron. A different problem always sounds.

**Fails open on purpose.** Without Redis there is nowhere to remember what was
sent, so everything is sent. Between a noisy channel and a mute one, the noisy
one can be fixed by reading it.
"""

import logging

from app.utils import cache

logger = logging.getLogger(__name__)

# How long a repetition stays silent. Long enough to group an incident's burst,
# short enough that a problem still alive sounds again within the same shift.
DEFAULT_WINDOW_SECONDS = 1800

_PREFIX = "alert:budget:"


def should_send(key: str, window_seconds: int = DEFAULT_WINDOW_SECONDS) -> bool:
    """Does this alert go out, or is it a repetition of one that already did?

    `key` identifies the **problem**, not the message: two different texts from
    the same dead cron share a key and don't sound twice.
    """
    client = cache.get_redis_client()
    if client is None:
        return True

    try:
        # SET NX is atomic: two workers failing at once send one alert, not
        # two. GET + SET would race exactly when there's the most noise.
        first = client.set(f"{_PREFIX}{key}", "1", nx=True, ex=window_seconds)
        return bool(first)
    except Exception:
        logger.warning("Could not consult the alert noise budget", exc_info=True)
        return True
