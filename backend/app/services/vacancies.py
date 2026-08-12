from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import ApplicationStatus, QueueItemStatus
from app.core.timeutil import msk_today_start_utc_naive, utc_now_naive
from app.models import Application, ApplyQueueItem, Vacancy
from app.schemas import DashboardStats, VacancyOut
from app.services.currency import rub_rate_case, salary_in_rub
from app.services.settings_service import get_or_create_settings


def _salary_rub_column(column: Any) -> Any:
    return column * rub_rate_case(Vacancy.currency)


def vacancy_to_out(
    v: Vacancy,
    *,
    matched_profiles: list[str] | None = None,
    application_status: str | None = None,
) -> VacancyOut:
    rub_from, rub_to, original = salary_in_rub(v.salary_from, v.salary_to, v.currency)
    return VacancyOut(
        id=v.id,
        source=v.source,
        source_vacancy_id=v.source_vacancy_id,
        url=v.url,
        title=v.title,
        company=v.company,
        description=v.description,
        salary_from=rub_from,
        salary_to=rub_to,
        currency="RUB" if rub_from is not None or rub_to is not None else v.currency,
        original_currency=original,
        city=v.city,
        remote=v.remote,
        work_format=v.work_format,
        employment_type=v.employment_type,
        experience=v.experience,
        published_at=v.published_at,
        collected_at=v.collected_at,
        skills=v.skills,
        status=v.status,
        matched_profiles=matched_profiles or [],
        application_status=application_status,
        created_at=v.created_at,
        updated_at=v.updated_at,
    )


async def get_dashboard_stats(session: AsyncSession) -> DashboardStats:
    settings = await get_or_create_settings(session)
    today = msk_today_start_utc_naive()

    total = (await session.execute(select(func.count(Vacancy.id)))).scalar_one()
    new_today = (
        await session.execute(
            select(func.count(Vacancy.id)).where(Vacancy.collected_at >= today)
        )
    ).scalar_one()
    matched = (
        await session.execute(
            select(func.count(Vacancy.id)).where(Vacancy.status == "matched")
        )
    ).scalar_one()

    apps_total = (await session.execute(select(func.count(Application.id)))).scalar_one()
    responses = (
        await session.execute(
            select(func.count(Application.id)).where(
                Application.status.in_(
                    [
                        ApplicationStatus.RESPONSE,
                        ApplicationStatus.VIEWED,
                        ApplicationStatus.INTERVIEW,
                        ApplicationStatus.TEST_TASK,
                        ApplicationStatus.OFFER,
                    ]
                )
            )
        )
    ).scalar_one()
    interviews = (
        await session.execute(
            select(func.count(Application.id)).where(
                Application.status == ApplicationStatus.INTERVIEW
            )
        )
    ).scalar_one()
    offers = (
        await session.execute(
            select(func.count(Application.id)).where(Application.status == ApplicationStatus.OFFER)
        )
    ).scalar_one()
    queue_pending = (
        await session.execute(
            select(func.count(ApplyQueueItem.id)).where(
                ApplyQueueItem.status == QueueItemStatus.PENDING
            )
        )
    ).scalar_one()

    return DashboardStats(
        total_vacancies=total,
        new_today=new_today,
        matched=matched,
        applications=apps_total,
        responses=responses,
        interviews=interviews,
        offers=offers,
        last_sync_at=settings.last_sync_at,
        next_sync_at=settings.next_sync_at,
        system_status=settings.system_status,
        global_auto_apply=settings.global_auto_apply,
        dry_run=settings.dry_run,
        sync_in_progress=settings.sync_in_progress,
        queue_pending=queue_pending,
    )


def _as_list(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items = value
    else:
        items = str(value).split(",")
    return [x.strip() for x in items if x and str(x).strip()]


def _as_int_list(value: str | list[str] | list[int] | int | None) -> list[int]:
    if value is None:
        return []
    if isinstance(value, int):
        return [value]
    if isinstance(value, list):
        raw = value
    else:
        raw = str(value).split(",")
    out: list[int] = []
    for item in raw:
        try:
            out.append(int(str(item).strip()))
        except (TypeError, ValueError):
            continue
    return out


def build_vacancy_filters(
    *,
    source: str | list[str] | None = None,
    status: str | list[str] | None = None,
    q: str | None = None,
    city: str | list[str] | None = None,
    work_format: str | list[str] | None = None,
    remote: bool | None = None,
    experience: str | list[str] | None = None,
    salary_from: int | None = None,
    salary_to: int | None = None,
    currency: str | None = None,
    skill: str | list[str] | None = None,
    role: str | list[str] | None = None,
    company: str | None = None,
    max_age_hours: int | None = None,
    has_salary: bool | None = None,
    employment_type: str | list[str] | None = None,
    now: datetime | None = None,
) -> list[Any]:
    filters: list[Any] = []
    sources = _as_list(source)
    statuses = _as_list(status)
    cities = _as_list(city)
    work_formats = _as_list(work_format)
    experiences = _as_list(experience)
    skills = _as_list(skill)
    roles = _as_list(role)
    employment_types = _as_list(employment_type)

    if sources:
        filters.append(Vacancy.source.in_(sources))
    if statuses:
        filters.append(Vacancy.status.in_(statuses))
    if cities:
        filters.append(or_(*[Vacancy.city.ilike(f"%{c}%") for c in cities]))
    if work_formats:
        fmt_clauses: list[Any] = []
        for fmt in work_formats:
            if fmt == "remote":
                fmt_clauses.append(or_(Vacancy.remote.is_(True), Vacancy.work_format == "remote"))
            else:
                fmt_clauses.append(Vacancy.work_format == fmt)
        filters.append(or_(*fmt_clauses))
    elif remote is True:
        filters.append(or_(Vacancy.remote.is_(True), Vacancy.work_format == "remote"))
    elif remote is False:
        filters.append(Vacancy.remote.is_(False))
    if experiences:
        filters.append(Vacancy.experience.in_(experiences))
    if salary_from is not None:
        rub_to = _salary_rub_column(Vacancy.salary_to)
        rub_from_col = _salary_rub_column(Vacancy.salary_from)
        filters.append(
            or_(
                rub_to >= salary_from,
                and_(Vacancy.salary_to.is_(None), rub_from_col >= salary_from),
            )
        )
    if salary_to is not None:
        rub_from_col = _salary_rub_column(Vacancy.salary_from)
        rub_to = _salary_rub_column(Vacancy.salary_to)
        filters.append(
            or_(
                rub_from_col <= salary_to,
                and_(Vacancy.salary_from.is_(None), rub_to <= salary_to),
            )
        )
    # currency filter is ignored for feed: salaries are normalized to RUB
    if currency and currency.upper() not in {"RUB", "RUR"}:
        filters.append(func.upper(Vacancy.currency) == currency.upper())
    elif currency and currency.upper() in {"RUB", "RUR"}:
        # show all currencies converted to RUB — no hard filter
        pass
    if skills:
        skill_clauses: list[Any] = []
        for s in skills:
            like = f"%{s}%"
            skill_clauses.append(
                or_(
                    Vacancy.skills.any(s),
                    Vacancy.title.ilike(like),
                    Vacancy.description.ilike(like),
                )
            )
        filters.append(or_(*skill_clauses))
    if roles:
        filters.append(or_(*[Vacancy.title.ilike(f"%{r}%") for r in roles]))
    if company:
        filters.append(Vacancy.company.ilike(f"%{company}%"))
    if has_salary is True:
        filters.append(or_(Vacancy.salary_from.is_not(None), Vacancy.salary_to.is_not(None)))
    if has_salary is False:
        filters.append(and_(Vacancy.salary_from.is_(None), Vacancy.salary_to.is_(None)))
    if employment_types:
        filters.append(or_(*[Vacancy.employment_type.ilike(f"%{e}%") for e in employment_types]))
    if max_age_hours is not None:
        cutoff = (now or utc_now_naive()) - timedelta(hours=max_age_hours)
        filters.append(Vacancy.published_at >= cutoff)
    if q:
        like = f"%{q}%"
        filters.append(
            or_(
                Vacancy.title.ilike(like),
                Vacancy.company.ilike(like),
                Vacancy.description.ilike(like),
                func.array_to_string(Vacancy.skills, " ").ilike(like),
            )
        )
    return filters


async def list_vacancies(
    session: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 20,
    source: str | list[str] | None = None,
    status: str | list[str] | None = None,
    q: str | None = None,
    city: str | list[str] | None = None,
    work_format: str | list[str] | None = None,
    remote: bool | None = None,
    experience: str | list[str] | None = None,
    salary_from: int | None = None,
    salary_to: int | None = None,
    currency: str | None = None,
    skill: str | list[str] | None = None,
    role: str | list[str] | None = None,
    company: str | None = None,
    max_age_hours: int | None = None,
    has_salary: bool | None = None,
    employment_type: str | list[str] | None = None,
    application_status: str | list[str] | None = None,
    profile_id: int | str | list[int] | list[str] | None = None,
    sort: str = "published_at",
) -> tuple[list[VacancyOut], int]:
    stmt = select(Vacancy)
    count_stmt = select(func.count(func.distinct(Vacancy.id)))
    filters = build_vacancy_filters(
        source=source,
        status=status,
        q=q,
        city=city,
        work_format=work_format,
        remote=remote,
        experience=experience,
        salary_from=salary_from,
        salary_to=salary_to,
        currency=currency,
        skill=skill,
        role=role,
        company=company,
        max_age_hours=max_age_hours,
        has_salary=has_salary,
        employment_type=employment_type,
    )

    app_statuses = _as_list(application_status)
    profile_ids = _as_int_list(profile_id)
    if app_statuses or profile_ids:
        stmt = stmt.join(Application, Application.vacancy_id == Vacancy.id)
        count_stmt = count_stmt.join(Application, Application.vacancy_id == Vacancy.id)
        if app_statuses:
            filters.append(Application.status.in_(app_statuses))
        if profile_ids:
            filters.append(Application.profile_id.in_(profile_ids))

    if filters:
        stmt = stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)

    total = (await session.execute(count_stmt)).scalar_one()

    order = Vacancy.published_at.desc().nullslast()
    if sort == "salary":
        order = _salary_rub_column(Vacancy.salary_from).desc().nullslast()
    elif sort == "collected_at":
        order = Vacancy.collected_at.desc()
    elif sort == "title":
        order = Vacancy.title.asc()

    result = await session.execute(
        stmt.order_by(order, Vacancy.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    vacancies = list(result.unique().scalars().all())

    # Attach application status
    vac_ids = [v.id for v in vacancies]
    apps_by_vac: dict[int, Application] = {}
    if vac_ids:
        apps = (
            await session.execute(
                select(Application)
                .options(selectinload(Application.profile))
                .where(Application.vacancy_id.in_(vac_ids))
                .order_by(Application.id.desc())
            )
        ).scalars().all()
        for app in apps:
            apps_by_vac.setdefault(app.vacancy_id, app)

    items: list[VacancyOut] = []
    for v in vacancies:
        app = apps_by_vac.get(v.id)
        matched = []
        if app and app.profile:
            matched = [app.profile.name]
        items.append(
            vacancy_to_out(
                v,
                matched_profiles=matched,
                application_status=app.status if app else None,
            )
        )
    return items, total


async def get_filter_options(session: AsyncSession) -> dict[str, list[str]]:
    city_rows = (
        await session.execute(
            select(Vacancy.city, func.count(Vacancy.id))
            .where(Vacancy.city.is_not(None))
            .where(Vacancy.city != "")
            .group_by(Vacancy.city)
            .order_by(func.count(Vacancy.id).desc())
            .limit(40)
        )
    ).all()
    skill_col = func.unnest(Vacancy.skills).label("skill")
    skill_rows = (
        await session.execute(
            select(skill_col, func.count())
            .where(Vacancy.skills.is_not(None))
            .group_by(skill_col)
            .order_by(func.count().desc())
            .limit(50)
        )
    ).all()
    return {
        "cities": [row[0] for row in city_rows if row[0]],
        "skills": [row[0] for row in skill_rows if row[0]],
    }
