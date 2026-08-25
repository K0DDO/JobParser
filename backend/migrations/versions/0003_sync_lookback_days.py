"""Add sync_lookback_days to app settings.

Revision ID: 0003_sync_lookback_days
Revises: 0002_city_text
Create Date: 2026-08-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_sync_lookback_days"
down_revision: Union[str, None] = "0002_city_text"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column(
            "sync_lookback_days",
            sa.Integer(),
            nullable=False,
            server_default="7",
        ),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "sync_lookback_days")
