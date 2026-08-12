from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.core.timeutil import msk_isoformat


class _MskJsonMixin(BaseModel):
    """Serialize all known datetime fields to Europe/Moscow ISO (+03:00)."""

    @field_serializer(
        "published_at",
        "collected_at",
        "created_at",
        "updated_at",
        "applied_at",
        "response_at",
        "last_sync_at",
        "next_sync_at",
        mode="plain",
        when_used="always",
        check_fields=False,
    )
    def _serialize_msk_dt(self, value: datetime | None) -> str | None:
        return msk_isoformat(value)


class VacancyData(BaseModel):
    """Normalized vacancy payload from any source parser."""

    source: str
    source_vacancy_id: str
    url: str
    title: str
    company: str | None = None
    description: str | None = None
    salary_from: int | None = None
    salary_to: int | None = None
    currency: str | None = None
    city: str | None = None
    remote: bool = False
    work_format: str = "unknown"
    employment_type: str | None = None
    experience: str = "unknown"
    published_at: datetime | None = None
    skills: list[str] = Field(default_factory=list)
    contacts: dict[str, Any] | None = None
    raw_data: dict[str, Any] | None = None
    source_metadata: dict[str, Any] | None = None


class VacancyOut(_MskJsonMixin):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    source_vacancy_id: str
    url: str
    title: str
    company: str | None
    description: str | None
    salary_from: int | None
    salary_to: int | None
    currency: str | None
    original_currency: str | None = None
    city: str | None
    remote: bool
    work_format: str
    employment_type: str | None
    experience: str
    published_at: datetime | None
    collected_at: datetime
    skills: list[str] | None
    status: str
    matched_profiles: list[str] = Field(default_factory=list)
    application_status: str | None = None
    created_at: datetime
    updated_at: datetime


class VacancyListResponse(BaseModel):
    items: list[VacancyOut]
    total: int
    page: int
    page_size: int


class VacancyFilterOptions(BaseModel):
    cities: list[str]
    skills: list[str]


class SearchProfileCreate(BaseModel):
    name: str
    is_active: bool = True
    include_skills: list[str] | None = None
    exclude_skills: list[str] | None = None
    roles: list[str] | None = None
    salary_from: int | None = None
    salary_to: int | None = None
    currency: str = "RUB"
    experience_levels: list[str] | None = None
    work_formats: list[str] | None = None
    cities: list[str] | None = None
    sources: list[str] | None = None
    max_age_hours: int | None = None
    auto_apply_enabled: bool = False
    daily_apply_limit: int = 30
    min_vacancy_age_hours: int | None = None
    max_vacancy_age_hours: int | None = None
    no_reapply: bool = True
    max_company_applies_per_day: int | None = None
    allowed_apply_sources: list[str] | None = None
    working_hours_start: str | None = None
    working_hours_end: str | None = None
    cover_letter: str | None = None


class SearchProfileUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    include_skills: list[str] | None = None
    exclude_skills: list[str] | None = None
    roles: list[str] | None = None
    salary_from: int | None = None
    salary_to: int | None = None
    currency: str | None = None
    experience_levels: list[str] | None = None
    work_formats: list[str] | None = None
    cities: list[str] | None = None
    sources: list[str] | None = None
    max_age_hours: int | None = None
    auto_apply_enabled: bool | None = None
    daily_apply_limit: int | None = None
    min_vacancy_age_hours: int | None = None
    max_vacancy_age_hours: int | None = None
    no_reapply: bool | None = None
    max_company_applies_per_day: int | None = None
    allowed_apply_sources: list[str] | None = None
    working_hours_start: str | None = None
    working_hours_end: str | None = None
    cover_letter: str | None = None


class SearchProfileOut(SearchProfileCreate, _MskJsonMixin):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class ApplicationOut(_MskJsonMixin):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vacancy_id: int
    profile_id: int | None
    status: str
    applied_at: datetime | None
    response_at: datetime | None
    notes: str | None
    is_auto: bool
    is_dry_run: bool
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    vacancy_title: str | None = None
    vacancy_company: str | None = None
    vacancy_source: str | None = None
    vacancy_url: str | None = None
    profile_name: str | None = None


class ApplicationUpdate(BaseModel):
    status: str | None = None
    notes: str | None = None


class ApplicationEventOut(_MskJsonMixin):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    event_type: str
    message: str
    old_status: str | None
    new_status: str | None
    created_at: datetime


class SourceOut(_MskJsonMixin):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    display_name: str
    parsing_enabled: bool
    auto_apply_enabled: bool
    auto_apply_supported: bool
    status: str
    last_sync_at: datetime | None
    last_error: str | None
    found_today: int
    connected: bool = False


class SourceUpdate(BaseModel):
    parsing_enabled: bool | None = None
    auto_apply_enabled: bool | None = None


class SettingsOut(_MskJsonMixin):
    model_config = ConfigDict(from_attributes=True)

    sync_interval_minutes: int
    timezone: str
    notifications_enabled: bool
    global_auto_apply: bool
    dry_run: bool
    global_daily_limit: int
    working_hours_start: str | None
    working_hours_end: str | None
    last_sync_at: datetime | None
    next_sync_at: datetime | None
    sync_in_progress: bool
    system_status: str


class SettingsUpdate(BaseModel):
    sync_interval_minutes: int | None = None
    timezone: str | None = None
    notifications_enabled: bool | None = None
    dry_run: bool | None = None
    global_daily_limit: int | None = None
    working_hours_start: str | None = None
    working_hours_end: str | None = None


class SyncStatusOut(_MskJsonMixin):
    sync_in_progress: bool
    last_sync_at: datetime | None
    next_sync_at: datetime | None
    system_status: str


class DashboardStats(_MskJsonMixin):
    total_vacancies: int
    new_today: int
    matched: int
    applications: int
    responses: int
    interviews: int
    offers: int
    last_sync_at: datetime | None
    next_sync_at: datetime | None
    system_status: str
    global_auto_apply: bool
    dry_run: bool
    sync_in_progress: bool
    queue_pending: int


class SystemLogOut(_MskJsonMixin):
    model_config = ConfigDict(from_attributes=True)

    id: int
    level: str
    category: str
    message: str
    details: dict[str, Any] | None
    created_at: datetime


class NotificationOut(_MskJsonMixin):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    message: str
    is_read: bool
    created_at: datetime


class MessageOut(BaseModel):
    message: str
    detail: str | None = None


class ApplyRequest(BaseModel):
    profile_id: int | None = None
    cover_letter: str | None = None
