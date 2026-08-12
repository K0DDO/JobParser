from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import utcnow
from app.db.session import Base


class Vacancy(Base):
    __tablename__ = "vacancies"
    __table_args__ = (
        UniqueConstraint("source", "source_vacancy_id", name="uq_vacancy_source_id"),
        Index("ix_vacancies_source", "source"),
        Index("ix_vacancies_source_vacancy_id", "source_vacancy_id"),
        Index("ix_vacancies_published_at", "published_at"),
        Index("ix_vacancies_company", "company"),
        Index("ix_vacancies_status", "status"),
        Index("ix_vacancies_canonical_url", "canonical_url"),
        Index("ix_vacancies_fingerprint", "fingerprint"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_vacancy_id: Mapped[str] = mapped_column(String(128), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)

    title: Mapped[str] = mapped_column(String(512), nullable=False)
    company: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    salary_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_to: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)

    city: Mapped[str | None] = mapped_column(String(256), nullable=True)
    remote: Mapped[bool] = mapped_column(Boolean, default=False)
    work_format: Mapped[str] = mapped_column(String(32), default="unknown")
    employment_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    experience: Mapped[str] = mapped_column(String(32), default="unknown")

    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    skills: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    contacts: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    source_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    status: Mapped[str] = mapped_column(String(32), default="new", index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    applications: Mapped[list["Application"]] = relationship(back_populates="vacancy")


class SearchProfile(Base):
    __tablename__ = "search_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    include_skills: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    exclude_skills: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    roles: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    salary_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_to: Mapped[int | None] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="RUB")

    experience_levels: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    work_formats: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    cities: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    sources: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    max_age_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Per-profile auto-apply
    auto_apply_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    daily_apply_limit: Mapped[int] = mapped_column(Integer, default=30)
    min_vacancy_age_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_vacancy_age_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    no_reapply: Mapped[bool] = mapped_column(Boolean, default=True)
    max_company_applies_per_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allowed_apply_sources: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    working_hours_start: Mapped[str | None] = mapped_column(String(5), nullable=True)  # HH:MM
    working_hours_end: Mapped[str | None] = mapped_column(String(5), nullable=True)
    cover_letter: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    applications: Mapped[list["Application"]] = relationship(back_populates="profile")


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint("vacancy_id", "profile_id", name="uq_application_vacancy_profile"),
        Index("ix_applications_status", "status"),
        Index("ix_applications_profile_id", "profile_id"),
        Index("ix_applications_vacancy_id", "vacancy_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id"), nullable=False)
    profile_id: Mapped[int | None] = mapped_column(ForeignKey("search_profiles.id"), nullable=True)

    status: Mapped[str] = mapped_column(String(32), default="discovered")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    response_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_auto: Mapped[bool] = mapped_column(Boolean, default=False)
    is_dry_run: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    vacancy: Mapped["Vacancy"] = relationship(back_populates="applications")
    profile: Mapped["SearchProfile | None"] = relationship(back_populates="applications")
    events: Mapped[list["ApplicationEvent"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )


class ApplicationEvent(Base):
    __tablename__ = "application_events"
    __table_args__ = (Index("ix_application_events_application_id", "application_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    old_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    application: Mapped["Application"] = relationship(back_populates="events")


class SourceConfig(Base):
    __tablename__ = "source_configs"
    __table_args__ = (UniqueConstraint("name", name="uq_source_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    parsing_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_apply_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_apply_supported: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="ready")  # ready|partial|unavailable
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    found_today: Mapped[int] = mapped_column(Integer, default=0)
    settings: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AppSettings(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sync_interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow")
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    global_auto_apply: Mapped[bool] = mapped_column(Boolean, default=False)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True)
    global_daily_limit: Mapped[int] = mapped_column(Integer, default=50)
    working_hours_start: Mapped[str | None] = mapped_column(String(5), nullable=True)
    working_hours_end: Mapped[str | None] = mapped_column(String(5), nullable=True)

    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sync_in_progress: Mapped[bool] = mapped_column(Boolean, default=False)
    system_status: Mapped[str] = mapped_column(String(32), default="ok")

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class SystemLog(Base):
    __tablename__ = "system_logs"
    __table_args__ = (Index("ix_system_logs_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    level: Mapped[str] = mapped_column(String(16), default="info")
    category: Mapped[str] = mapped_column(String(64), default="system")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ApplyQueueItem(Base):
    __tablename__ = "apply_queue"
    __table_args__ = (
        Index("ix_apply_queue_status", "status"),
        UniqueConstraint("vacancy_id", "profile_id", name="uq_queue_vacancy_profile"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id"), nullable=False)
    profile_id: Mapped[int] = mapped_column(ForeignKey("search_profiles.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
