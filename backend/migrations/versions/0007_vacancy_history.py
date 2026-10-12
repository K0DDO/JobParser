"""Vacancy history: last_seen_at + removed_at soft-delete.

Revision ID: 0007_vacancy_history
Revises: 0006_telegram_filters_json
Create Date: 2026-10-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007_vacancy_history"
down_revision: Union[str, None] = "0006_telegram_filters_json"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("vacancies", sa.Column("last_seen_at", sa.DateTime(), nullable=True))
    op.add_column("vacancies", sa.Column("removed_at", sa.DateTime(), nullable=True))
    op.create_index("ix_vacancies_removed_at", "vacancies", ["removed_at"])
    op.create_index("ix_vacancies_last_seen_at", "vacancies", ["last_seen_at"])
    # Existing rows count as seen at created_at / updated_at
    op.execute(
        """
        UPDATE vacancies
        SET last_seen_at = COALESCE(updated_at, created_at, NOW())
        WHERE last_seen_at IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_vacancies_last_seen_at", table_name="vacancies")
    op.drop_index("ix_vacancies_removed_at", table_name="vacancies")
    op.drop_column("vacancies", "removed_at")
    op.drop_column("vacancies", "last_seen_at")
