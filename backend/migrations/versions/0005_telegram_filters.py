"""Add telegram filter selections to app settings.

Revision ID: 0005_telegram_filters
Revises: 0004_telegram_notified_at
Create Date: 2026-10-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_telegram_filters"
down_revision: Union[str, None] = "0004_telegram_notified_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("telegram_roles", postgresql.ARRAY(sa.String()), nullable=True),
    )
    op.add_column(
        "app_settings",
        sa.Column("telegram_work_formats", postgresql.ARRAY(sa.String()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "telegram_work_formats")
    op.drop_column("app_settings", "telegram_roles")
