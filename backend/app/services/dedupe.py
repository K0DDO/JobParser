from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Vacancy
from app.schemas import VacancyData
from app.services.normalize import build_fingerprint, canonicalize_url, normalize_vacancy


async def find_existing_vacancy(session: AsyncSession, data: VacancyData) -> Vacancy | None:
    """
    Dedup priority:
    1. source + source_vacancy_id
    2. canonical URL
    3. fingerprint (company+title+location+salary+source)
    """
    result = await session.execute(
        select(Vacancy).where(
            Vacancy.source == data.source,
            Vacancy.source_vacancy_id == data.source_vacancy_id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    canonical = canonicalize_url(data.url)
    result = await session.execute(select(Vacancy).where(Vacancy.canonical_url == canonical))
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    fingerprint = build_fingerprint(data)
    result = await session.execute(select(Vacancy).where(Vacancy.fingerprint == fingerprint))
    return result.scalar_one_or_none()


def apply_vacancy_update(vacancy: Vacancy, data: VacancyData) -> Vacancy:
    vacancy.url = data.url
    vacancy.canonical_url = canonicalize_url(data.url)
    vacancy.fingerprint = build_fingerprint(data)
    vacancy.title = data.title
    vacancy.company = data.company
    vacancy.description = data.description
    vacancy.salary_from = data.salary_from
    vacancy.salary_to = data.salary_to
    vacancy.currency = data.currency
    vacancy.city = data.city
    vacancy.remote = data.remote
    vacancy.work_format = data.work_format
    vacancy.employment_type = data.employment_type
    vacancy.experience = data.experience
    vacancy.published_at = data.published_at
    vacancy.skills = data.skills or []
    vacancy.contacts = data.contacts
    vacancy.raw_data = data.raw_data
    vacancy.source_metadata = data.source_metadata
    return vacancy


async def upsert_vacancy(session: AsyncSession, data: VacancyData) -> tuple[Vacancy, bool]:
    """
    Insert or update vacancy. Returns (vacancy, created).
    """
    data = normalize_vacancy(data)
    existing = await find_existing_vacancy(session, data)
    if existing:
        apply_vacancy_update(existing, data)
        # Keep original source identity if matched via URL/fingerprint across same source
        if existing.source == data.source:
            existing.source_vacancy_id = data.source_vacancy_id
        await session.flush()
        return existing, False

    vacancy = Vacancy(
        source=data.source,
        source_vacancy_id=data.source_vacancy_id,
        url=data.url,
        canonical_url=canonicalize_url(data.url),
        fingerprint=build_fingerprint(data),
        title=data.title,
        company=data.company,
        description=data.description,
        salary_from=data.salary_from,
        salary_to=data.salary_to,
        currency=data.currency,
        city=data.city,
        remote=data.remote,
        work_format=data.work_format,
        employment_type=data.employment_type,
        experience=data.experience,
        published_at=data.published_at,
        skills=data.skills or [],
        contacts=data.contacts,
        raw_data=data.raw_data,
        source_metadata=data.source_metadata,
        status="new",
    )
    session.add(vacancy)
    await session.flush()
    return vacancy, True
