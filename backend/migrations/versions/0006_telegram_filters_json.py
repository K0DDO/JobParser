"""Store full Telegram filter state as JSONB.

Revision ID: 0006_telegram_filters_json
Revises: 0005_telegram_filters
Create Date: 2026-10-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_telegram_filters_json"
down_revision: Union[str, None] = "0005_telegram_filters"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("telegram_filters", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    # Migrate previous role/format arrays into JSON if present.
    op.execute(
        """
        UPDATE app_settings
        SET telegram_filters = jsonb_strip_nulls(
            jsonb_build_object(
                'roles', COALESCE(to_jsonb(telegram_roles), '[]'::jsonb),
                'work_formats', COALESCE(to_jsonb(telegram_work_formats), '[]'::jsonb)
            )
        )
        WHERE telegram_filters IS NULL
          AND (telegram_roles IS NOT NULL OR telegram_work_formats IS NOT NULL)
        """
    )


def downgrade() -> None:
    op.drop_column("app_settings", "telegram_filters")
