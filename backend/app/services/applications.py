from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import ApplicationStatus
from app.models import Application, ApplicationEvent, Vacancy
from app.parsers import get_source
from app.schemas import VacancyData
from app.services.hh_auth import get_hh_source, resolve_access_token


async def get_application_for_vacancy(
    session: AsyncSession,
    vacancy_id: int,
    profile_id: int | None = None,
) -> Application | None:
    stmt = select(Application).where(Application.vacancy_id == vacancy_id)
    if profile_id is not None:
        stmt = stmt.where(Application.profile_id == profile_id)
    result = await session.execute(stmt.order_by(Application.id.asc()))
    return result.scalars().first()


async def has_any_application(session: AsyncSession, vacancy_id: int) -> bool:
    result = await session.execute(
        select(Application.id).where(Application.vacancy_id == vacancy_id).limit(1)
    )
    return result.scalar_one_or_none() is not None


async def add_event(
    session: AsyncSession,
    application: Application,
    event_type: str,
    message: str,
    *,
    old_status: str | None = None,
    new_status: str | None = None,
) -> ApplicationEvent:
    event = ApplicationEvent(
        application_id=application.id,
        event_type=event_type,
        message=message,
        old_status=old_status,
        new_status=new_status,
    )
    session.add(event)
    await session.flush()
    return event


async def create_or_get_application(
    session: AsyncSession,
    vacancy: Vacancy,
    profile_id: int | None,
    *,
    status: str = ApplicationStatus.DISCOVERED,
    is_auto: bool = False,
    is_dry_run: bool = False,
) -> tuple[Application, bool]:
    existing = await get_application_for_vacancy(session, vacancy.id, profile_id)
    if existing:
        return existing, False

    app = Application(
        vacancy_id=vacancy.id,
        profile_id=profile_id,
        status=status,
        is_auto=is_auto,
        is_dry_run=is_dry_run,
    )
    session.add(app)
    await session.flush()
    await add_event(
        session,
        app,
        "created",
        f"Application created with status {status}",
        new_status=status,
    )
    return app, True


async def transition_status(
    session: AsyncSession,
    application: Application,
    new_status: str,
    message: str,
) -> Application:
    old = application.status
    application.status = new_status
    await add_event(
        session,
        application,
        "status_change",
        message,
        old_status=old,
        new_status=new_status,
    )
    await session.flush()
    return application


async def manual_apply(
    session: AsyncSession,
    vacancy: Vacancy,
    profile_id: int | None = None,
    cover_letter: str | None = None,
    *,
    force_dry_run: bool = False,
) -> Application:
    """
    Manual apply for a vacancy.
    If source supports apply and credentials exist — attempts real apply.
    Otherwise records application as applied/failed with a clear message.
    """
    if await has_any_application(session, vacancy.id):
        existing = await get_application_for_vacancy(session, vacancy.id)
        assert existing is not None
        return existing

    application, _ = await create_or_get_application(
        session,
        vacancy,
        profile_id,
        status=ApplicationStatus.QUEUED,
        is_auto=False,
        is_dry_run=force_dry_run,
    )

    if force_dry_run:
        application.is_dry_run = True
        application.applied_at = datetime.utcnow()
        await transition_status(
            session,
            application,
            ApplicationStatus.DRY_RUN,
            "Dry run: application would be sent (manual)",
        )
        return application

    source = get_source(vacancy.source)
    if source is None or not source.auto_apply_supported:
        application.error_message = (
            f"Auto-apply is not supported for source '{vacancy.source}'. "
            "Open the vacancy URL and apply manually; status set to applied for tracking."
        )
        application.applied_at = datetime.utcnow()
        application.notes = "Tracked as applied (external/manual)"
        await transition_status(
            session,
            application,
            ApplicationStatus.APPLIED,
            "Marked as applied for tracking (source does not support API apply)",
        )
        return application

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
        await source.apply_to_vacancy(vacancy_data, cover_letter=cover_letter)
        application.applied_at = datetime.utcnow()
        await transition_status(
            session,
            application,
            ApplicationStatus.APPLIED,
            "Application sent successfully",
        )
    except Exception as exc:  # noqa: BLE001 — surface clear error to user
        application.error_message = str(exc)
        await transition_status(
            session,
            application,
            ApplicationStatus.FAILED,
            f"Apply failed: {exc}",
        )
    return application


async def load_application(session: AsyncSession, application_id: int) -> Application | None:
    result = await session.execute(
        select(Application)
        .options(selectinload(Application.vacancy), selectinload(Application.profile))
        .where(Application.id == application_id)
    )
    return result.scalar_one_or_none()
