"""Add telegram_notified_at to vacancies.

Revision ID: 0004_telegram_notified_at
Revises: 0003_sync_lookback_days
Create Date: 2026-10-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_telegram_notified_at"
down_revision: Union[str, None] = "0003_sync_lookback_days"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "vacancies",
        sa.Column("telegram_notified_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("vacancies", "telegram_notified_at")
