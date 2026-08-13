"""Widen vacancy city to Text so multi-location ATS blobs cannot abort sync.

Revision ID: 0002_city_text
Revises: 0001_initial
Create Date: 2026-08-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_city_text"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "vacancies",
        "city",
        existing_type=sa.String(length=256),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "vacancies",
        "city",
        existing_type=sa.Text(),
        type_=sa.String(length=256),
        existing_nullable=True,
    )
