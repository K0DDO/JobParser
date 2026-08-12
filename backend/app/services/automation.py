"""Auto-apply safety gates and queue worker."""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ApplicationStatus, QueueItemStatus
from app.models import Application, ApplyQueueItem, AppSettings, SearchProfile, SourceConfig, Vacancy
from app.parsers import get_source
from app.schemas import VacancyData
from app.services.applications import (
    add_event,
    create_or_get_application,
    has_any_application,
    transition_status,
)
from app.services.hh_auth import get_hh_source, resolve_access_token
from app.services.logging_service import add_log

logger = logging.getLogger(__name__)


def _parse_hhmm(value: str | None) -> time | None:
    if not value:
        return None
    try:
        hours, minutes = value.split(":")
        return time(int(hours), int(minutes))
    except (ValueError, TypeError):
        return None


def within_working_hours(
    now: datetime,
    start: str | None,
    end: str | None,
) -> bool:
    start_t = _parse_hhmm(start)
    end_t = _parse_hhmm(end)
    if start_t is None or end_t is None:
        return True
    current = now.time().replace(second=0, microsecond=0)
    if start_t <= end_t:
        return start_t <= current <= end_t
    # overnight window
    return current >= start_t or current <= end_t


async def count_applies_today(
    session: AsyncSession,
    *,
    profile_id: int | None = None,
    company: str | None = None,
) -> int:
    day_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    stmt = (
        select(func.count(Application.id))
        .where(Application.applied_at >= day_start)
        .where(Application.status.in_([ApplicationStatus.APPLIED, ApplicationStatus.DRY_RUN]))
        .where(Application.is_auto.is_(True))
    )
    if profile_id is not None:
        stmt = stmt.where(Application.profile_id == profile_id)
    if company is not None:
        stmt = stmt.join(Vacancy, Vacancy.id == Application.vacancy_id).where(
            Vacancy.company == company
        )
    result = await session.execute(stmt)
    return int(result.scalar_one())


class AutoApplyGuard:
    """Deterministic checks that must all pass before sending an auto-apply."""

    def __init__(self, settings: AppSettings):
        self.settings = settings

    def global_allowed(self) -> tuple[bool, str]:
        if not self.settings.global_auto_apply:
            return False, "Global Auto Apply is OFF"
        return True, "ok"

    async def can_enqueue(
        self,
        session: AsyncSession,
        vacancy: Vacancy,
        profile: SearchProfile,
        source: SourceConfig,
    ) -> tuple[bool, str]:
        allowed, reason = self.global_allowed()
        if not allowed:
            return False, reason

        if not profile.auto_apply_enabled:
            return False, f"Profile '{profile.name}' Auto Apply is OFF"

        if not source.auto_apply_enabled:
            return False, f"Source '{source.name}' Auto Apply is OFF"

        if not source.auto_apply_supported:
            return False, f"Source '{source.name}' does not support auto-apply"

        if profile.allowed_apply_sources and vacancy.source not in profile.allowed_apply_sources:
            return False, "Vacancy source is not in profile allowed_apply_sources"

        if await has_any_application(session, vacancy.id):
            return False, "Application already exists for this vacancy"

        now = datetime.utcnow()
        if vacancy.published_at:
            age_hours = (now - vacancy.published_at).total_seconds() / 3600
            if profile.min_vacancy_age_hours is not None and age_hours < profile.min_vacancy_age_hours:
                return False, "Vacancy is too new"
            if profile.max_vacancy_age_hours is not None and age_hours > profile.max_vacancy_age_hours:
                return False, "Vacancy is too old"

        wh_start = profile.working_hours_start or self.settings.working_hours_start
        wh_end = profile.working_hours_end or self.settings.working_hours_end
        if not within_working_hours(now, wh_start, wh_end):
            return False, "Outside working hours"

        return True, "ok"

    async def can_send(
        self,
        session: AsyncSession,
        vacancy: Vacancy,
        profile: SearchProfile,
    ) -> tuple[bool, str]:
        # Re-check global switch right before send (Emergency Stop)
        allowed, reason = self.global_allowed()
        if not allowed:
            return False, reason

        if not profile.auto_apply_enabled:
            return False, f"Profile '{profile.name}' Auto Apply is OFF"

        global_count = await count_applies_today(session)
        if global_count >= self.settings.global_daily_limit:
            return False, f"Global daily limit reached ({self.settings.global_daily_limit})"

        profile_count = await count_applies_today(session, profile_id=profile.id)
        if profile_count >= profile.daily_apply_limit:
            return False, f"Profile daily limit reached ({profile.daily_apply_limit})"

        if profile.max_company_applies_per_day and vacancy.company:
            company_count = await count_applies_today(
                session, profile_id=profile.id, company=vacancy.company
            )
            if company_count >= profile.max_company_applies_per_day:
                return False, "Company daily apply limit reached"

        if profile.no_reapply and await has_any_application(session, vacancy.id):
            return False, "Application already exists (no_reapply)"

        wh_start = profile.working_hours_start or self.settings.working_hours_start
        wh_end = profile.working_hours_end or self.settings.working_hours_end
        if not within_working_hours(datetime.utcnow(), wh_start, wh_end):
            return False, "Outside working hours"

        return True, "ok"


async def enqueue_apply(
    session: AsyncSession,
    vacancy: Vacancy,
    profile: SearchProfile,
) -> ApplyQueueItem | None:
    existing = await session.execute(
        select(ApplyQueueItem).where(
            ApplyQueueItem.vacancy_id == vacancy.id,
            ApplyQueueItem.profile_id == profile.id,
        )
    )
    if existing.scalar_one_or_none():
        return None

    item = ApplyQueueItem(
        vacancy_id=vacancy.id,
        profile_id=profile.id,
        status=QueueItemStatus.PENDING,
        scheduled_at=datetime.utcnow(),
    )
    session.add(item)
    await session.flush()
    return item


async def process_queue_item(session: AsyncSession, item: ApplyQueueItem, settings: AppSettings) -> None:
    guard = AutoApplyGuard(settings)
    vacancy = await session.get(Vacancy, item.vacancy_id)
    profile = await session.get(SearchProfile, item.profile_id)
    if vacancy is None or profile is None:
        item.status = QueueItemStatus.FAILED
        item.last_error = "Vacancy or profile missing"
        item.processed_at = datetime.utcnow()
        return

    item.status = QueueItemStatus.PROCESSING
    item.attempts += 1
    await session.flush()

    allowed, reason = await guard.can_send(session, vacancy, profile)
    if not allowed:
        item.status = QueueItemStatus.SKIPPED
        item.last_error = reason
        item.processed_at = datetime.utcnow()
        await add_log(session, f"Auto-apply skipped: {reason}", level="warning", category="auto_apply")
        return

    application, created = await create_or_get_application(
        session,
        vacancy,
        profile.id,
        status=ApplicationStatus.QUEUED,
        is_auto=True,
        is_dry_run=settings.dry_run,
    )
    if not created and application.status in {
        ApplicationStatus.APPLIED,
        ApplicationStatus.DRY_RUN,
        ApplicationStatus.QUEUED,
        ApplicationStatus.VIEWED,
        ApplicationStatus.RESPONSE,
        ApplicationStatus.INTERVIEW,
        ApplicationStatus.TEST_TASK,
        ApplicationStatus.OFFER,
    }:
        item.status = QueueItemStatus.SKIPPED
        item.last_error = "Duplicate application protection"
        item.processed_at = datetime.utcnow()
        return

    if settings.dry_run:
        application.is_dry_run = True
        application.is_auto = True
        application.applied_at = datetime.utcnow()
        await transition_status(
            session,
            application,
            ApplicationStatus.DRY_RUN,
            "Dry run: would send auto-apply (no real request)",
        )
        item.status = QueueItemStatus.DRY_RUN
        item.processed_at = datetime.utcnow()
        await add_log(
            session,
            f"Dry run auto-apply: {vacancy.title} @ {vacancy.company}",
            level="info",
            category="auto_apply",
        )
        return

    source = get_source(vacancy.source)
    if source is None or not source.auto_apply_supported:
        application.error_message = "Source does not support auto-apply"
        await transition_status(session, application, ApplicationStatus.FAILED, application.error_message)
        item.status = QueueItemStatus.FAILED
        item.last_error = application.error_message
        item.processed_at = datetime.utcnow()
        return

    if vacancy.source == "hh" and hasattr(source, "access_token"):
        hh_source = await get_hh_source(session)
        source.access_token = resolve_access_token(hh_source)

    vacancy_data = VacancyData(
        source=vacancy.source,
        source_vacancy_id=vacancy.source_vacancy_id,
        url=vacancy.url,
        title=vacancy.title,
        company=vacancy.company,
        description=vacancy.description,
        salary_from=vacancy.salary_from,
        salary_to=vacancy.salary_to,
        currency=vacancy.currency,
        city=vacancy.city,
        remote=vacancy.remote,
        work_format=vacancy.work_format,
        employment_type=vacancy.employment_type,
        experience=vacancy.experience,
        published_at=vacancy.published_at,
        skills=vacancy.skills or [],
    )

    try:
        await source.apply_to_vacancy(vacancy_data, cover_letter=profile.cover_letter)
        application.is_auto = True
        application.applied_at = datetime.utcnow()
        await transition_status(session, application, ApplicationStatus.APPLIED, "Auto-apply sent")
        item.status = QueueItemStatus.DONE
        item.processed_at = datetime.utcnow()
        await add_log(
            session,
            f"Auto-apply sent: {vacancy.title} @ {vacancy.company}",
            level="success",
            category="auto_apply",
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Auto-apply failed for vacancy %s", vacancy.id)
        application.error_message = str(exc)
        await transition_status(session, application, ApplicationStatus.FAILED, f"Auto-apply failed: {exc}")
        if item.attempts < item.max_attempts:
            item.status = QueueItemStatus.PENDING
            item.scheduled_at = datetime.utcnow() + timedelta(minutes=5 * item.attempts)
            item.last_error = str(exc)
        else:
            item.status = QueueItemStatus.FAILED
            item.last_error = str(exc)
            item.processed_at = datetime.utcnow()


async def process_pending_queue(session: AsyncSession, limit: int = 20) -> int:
    settings = (
        await session.execute(select(AppSettings).limit(1))
    ).scalar_one_or_none()
    if settings is None:
        return 0

    # Hard stop — never process if global auto apply is off
    if not settings.global_auto_apply:
        return 0

    result = await session.execute(
        select(ApplyQueueItem)
        .where(ApplyQueueItem.status == QueueItemStatus.PENDING)
        .where(ApplyQueueItem.scheduled_at <= datetime.utcnow())
        .order_by(ApplyQueueItem.id.asc())
        .limit(limit)
    )
    items = list(result.scalars().all())
    for item in items:
        # Re-load settings each item so Emergency Stop takes effect immediately
        settings = (await session.execute(select(AppSettings).limit(1))).scalar_one()
        if not settings.global_auto_apply:
            await add_log(
                session,
                "Emergency stop / Auto Apply OFF — remaining queue not processed",
                level="warning",
                category="auto_apply",
            )
            break
        await process_queue_item(session, item, settings)
    await session.commit()
    return len(items)


async def emergency_stop(session: AsyncSession) -> AppSettings:
    settings = (await session.execute(select(AppSettings).limit(1))).scalar_one()
    settings.global_auto_apply = False
    # Cancel pending queue items
    result = await session.execute(
        select(ApplyQueueItem).where(ApplyQueueItem.status == QueueItemStatus.PENDING)
    )
    for item in result.scalars().all():
        item.status = QueueItemStatus.SKIPPED
        item.last_error = "Emergency stop"
        item.processed_at = datetime.utcnow()
    await add_log(session, "EMERGENCY STOP: Auto Apply disabled", level="warning", category="auto_apply")
    await session.commit()
    return settings
