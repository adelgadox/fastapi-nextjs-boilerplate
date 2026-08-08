from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, String
from sqlalchemy.sql import func

from app.database import Base


class CronRun(Base):
    """Last successful run of each cron.

    Exists because absences go unnoticed: a cron that **never runs** raises no
    exception, so a failure-based alerting system stays perfectly silent while
    the work goes undone.

    One row per cron, written on successful completion. `created_at` matters as
    much as `last_success_at`: it distinguishes "just deployed, not due yet"
    from "hasn't run once in its whole window".
    """

    __tablename__ = "cron_runs"

    name = Column(String, primary_key=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    @property
    def reference_time(self) -> datetime:
        """Where lag is measured from: the last run, or creation if it never ran."""
        value = self.last_success_at or self.created_at
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
