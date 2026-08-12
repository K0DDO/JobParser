"""empty message

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vacancies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("source_vacancy_id", sa.String(length=128), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=True),
        sa.Column("fingerprint", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("company", sa.String(length=512), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("salary_from", sa.Integer(), nullable=True),
        sa.Column("salary_to", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("city", sa.String(length=256), nullable=True),
        sa.Column("remote", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("work_format", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("employment_type", sa.String(length=64), nullable=True),
        sa.Column("experience", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("collected_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("skills", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("contacts", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("source_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="new"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "source_vacancy_id", name="uq_vacancy_source_id"),
    )
    op.create_index("ix_vacancies_source", "vacancies", ["source"])
    op.create_index("ix_vacancies_source_vacancy_id", "vacancies", ["source_vacancy_id"])
    op.create_index("ix_vacancies_published_at", "vacancies", ["published_at"])
    op.create_index("ix_vacancies_company", "vacancies", ["company"])
    op.create_index("ix_vacancies_status", "vacancies", ["status"])
    op.create_index("ix_vacancies_canonical_url", "vacancies", ["canonical_url"])
    op.create_index("ix_vacancies_fingerprint", "vacancies", ["fingerprint"])

    op.create_table(
        "search_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("include_skills", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("exclude_skills", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("roles", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("salary_from", sa.Integer(), nullable=True),
        sa.Column("salary_to", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="RUB"),
        sa.Column("experience_levels", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("work_formats", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("cities", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("sources", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("max_age_hours", sa.Integer(), nullable=True),
        sa.Column("auto_apply_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("daily_apply_limit", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("min_vacancy_age_hours", sa.Integer(), nullable=True),
        sa.Column("max_vacancy_age_hours", sa.Integer(), nullable=True),
        sa.Column("no_reapply", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("max_company_applies_per_day", sa.Integer(), nullable=True),
        sa.Column("allowed_apply_sources", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("working_hours_start", sa.String(length=5), nullable=True),
        sa.Column("working_hours_end", sa.String(length=5), nullable=True),
        sa.Column("cover_letter", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "source_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=64), nullable=False),
        sa.Column("parsing_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("auto_apply_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("auto_apply_supported", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ready"),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("found_today", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_source_name"),
    )

    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sync_interval_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("timezone", sa.String(length=64), nullable=False, server_default="Europe/Moscow"),
        sa.Column("notifications_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("global_auto_apply", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("global_daily_limit", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("working_hours_start", sa.String(length=5), nullable=True),
        sa.Column("working_hours_end", sa.String(length=5), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column("next_sync_at", sa.DateTime(), nullable=True),
        sa.Column("sync_in_progress", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("system_status", sa.String(length=32), nullable=False, server_default="ok"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "system_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False, server_default="info"),
        sa.Column("category", sa.String(length=64), nullable=False, server_default="system"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_system_logs_created_at", "system_logs", ["created_at"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("vacancy_id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="discovered"),
        sa.Column("applied_at", sa.DateTime(), nullable=True),
        sa.Column("response_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_auto", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_dry_run", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["search_profiles.id"]),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vacancy_id", "profile_id", name="uq_application_vacancy_profile"),
    )
    op.create_index("ix_applications_status", "applications", ["status"])
    op.create_index("ix_applications_profile_id", "applications", ["profile_id"])
    op.create_index("ix_applications_vacancy_id", "applications", ["vacancy_id"])

    op.create_table(
        "application_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("old_status", sa.String(length=32), nullable=True),
        sa.Column("new_status", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_application_events_application_id", "application_events", ["application_id"])

    op.create_table(
        "apply_queue",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("vacancy_id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["search_profiles.id"]),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vacancy_id", "profile_id", name="uq_queue_vacancy_profile"),
    )
    op.create_index("ix_apply_queue_status", "apply_queue", ["status"])


def downgrade() -> None:
    op.drop_table("apply_queue")
    op.drop_table("application_events")
    op.drop_table("applications")
    op.drop_table("notifications")
    op.drop_table("system_logs")
    op.drop_table("app_settings")
    op.drop_table("source_configs")
    op.drop_table("search_profiles")
    op.drop_table("vacancies")
