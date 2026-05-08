"""add login lockout fields to users

Revision ID: 001_add_login_lockout
Revises:
Create Date: 2026-05-07
"""

from alembic import op
import sqlalchemy as sa

revision = "001_add_login_lockout"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("login_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("lockout_until", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "lockout_until")
    op.drop_column("users", "login_attempts")
