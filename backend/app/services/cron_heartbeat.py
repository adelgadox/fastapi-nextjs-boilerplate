"""Cron heartbeat.

The rest of observability fires when something fails. This covers the
opposite: when something **stops happening**, which raises no exception and
therefore triggers nothing.

Windows live in code, not the environment, because they belong to each cron's
schedule, not to whoever operates the deploy: if someone changes a purge's
hour, they change this table in the same commit.
"""

import logging
from datetime import datetime, timedelta, timezone

from app.models.cron_run import CronRun

logger = logging.getLogger(__name__)

# How long a cron may go without running before it's a problem. With slack over
# its real period: a daily cron delayed two hours by a deploy is not news; one
# a day and a half late is.
CRON_MAX_AGE: dict[str, timedelta] = {
    "purge_expired_tokens_cron": timedelta(hours=36),  # daily
    "heartbeat_watchdog_cron": timedelta(hours=3),     # hourly
}


def record_success(db, name: str) -> None:
    """Note that a cron finished well.

    Never raises: recording the heartbeat is the last thing a cron does, and
    if this blew up it would lose the signal of work that WAS done.
    """
    try:
        row = db.get(CronRun, name)
        if row is None:
            row = CronRun(name=name)
            db.add(row)
        row.last_success_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        logger.warning("Could not record heartbeat for %s", name, exc_info=True)


def stale_crons(db) -> list[str]:
    """The crons that have gone longer than their window without running.

    A cron with no row isn't reported: the row is born with the first record,
    and until then there's nothing to assert. A cron no longer in
    `CRON_MAX_AGE` isn't either, so an old row doesn't alert forever.
    """
    now = datetime.now(timezone.utc)
    stale = []
    for row in db.query(CronRun).all():
        max_age = CRON_MAX_AGE.get(row.name)
        if max_age is None:
            continue
        if now - row.reference_time > max_age:
            stale.append(row.name)
    return sorted(stale)
