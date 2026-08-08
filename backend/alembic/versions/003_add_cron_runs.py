"""add cron_runs heartbeat table

Revision ID: 003_add_cron_runs
Revises: 002_add_refresh_tokens
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa

revision = "003_add_cron_runs"
down_revision = "002_add_refresh_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cron_runs",
        sa.Column("name", sa.String(), primary_key=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("cron_runs")
