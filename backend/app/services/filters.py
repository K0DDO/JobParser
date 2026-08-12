from datetime import datetime, timedelta

from app.models import SearchProfile, Vacancy


def _text_blob(vacancy: Vacancy) -> str:
    parts = [
        vacancy.title or "",
        vacancy.description or "",
        " ".join(vacancy.skills or []),
        vacancy.company or "",
    ]
    return " ".join(parts).lower()


def matches_skills(vacancy: Vacancy, profile: SearchProfile) -> bool:
    blob = _text_blob(vacancy)
    skills = [s.lower() for s in (vacancy.skills or [])]

    for skill in profile.include_skills or []:
        s = skill.lower().strip()
        if not s:
            continue
        if s not in blob and s not in skills:
            return False

    for skill in profile.exclude_skills or []:
        s = skill.lower().strip()
        if not s:
            continue
        if s in blob or s in skills:
            return False

    return True


def matches_roles(vacancy: Vacancy, profile: SearchProfile) -> bool:
    roles = profile.roles or []
    if not roles:
        return True
    title = (vacancy.title or "").lower()
    return any(role.lower().strip() in title for role in roles if role.strip())


def matches_salary(vacancy: Vacancy, profile: SearchProfile) -> bool:
    from app.services.currency import salary_in_rub, to_rub

    vac_from, vac_to, _ = salary_in_rub(vacancy.salary_from, vacancy.salary_to, vacancy.currency)

    # No salary on vacancy → pass (user can tighten later)
    if vac_from is None and vac_to is None:
        return True

    profile_from = to_rub(profile.salary_from, profile.currency or "RUB")
    profile_to = to_rub(profile.salary_to, profile.currency or "RUB")

    if profile_from is not None:
        vac_max = vac_to if vac_to is not None else vac_from
        if vac_max is not None and vac_max < profile_from:
            return False

    if profile_to is not None:
        vac_min = vac_from if vac_from is not None else vac_to
        if vac_min is not None and vac_min > profile_to:
            return False

    return True


def matches_experience(vacancy: Vacancy, profile: SearchProfile) -> bool:
    levels = profile.experience_levels or []
    if not levels:
        return True
    return vacancy.experience in levels


def matches_work_format(vacancy: Vacancy, profile: SearchProfile) -> bool:
    formats = profile.work_formats or []
    if not formats:
        return True
    if vacancy.work_format in formats:
        return True
    if "remote" in formats and vacancy.remote:
        return True
    return False


def matches_city(vacancy: Vacancy, profile: SearchProfile) -> bool:
    cities = profile.cities or []
    if not cities:
        return True
    normalized = [c.lower().strip() for c in cities]
    if "любой" in normalized or "any" in normalized:
        return True
    city = (vacancy.city or "").lower().strip()
    if not city:
        return True
    return any(c in city or city in c for c in normalized)


def matches_source(vacancy: Vacancy, profile: SearchProfile) -> bool:
    sources = profile.sources or []
    if not sources:
        return True
    return vacancy.source in sources


def matches_age(vacancy: Vacancy, profile: SearchProfile, now: datetime | None = None) -> bool:
    max_age = profile.max_age_hours
    if max_age is None:
        return True
    if vacancy.published_at is None:
        return True
    now = now or datetime.utcnow()
    return vacancy.published_at >= now - timedelta(hours=max_age)


def vacancy_matches_profile(
    vacancy: Vacancy,
    profile: SearchProfile,
    now: datetime | None = None,
) -> bool:
    if not profile.is_active:
        return False
    return all(
        [
            matches_skills(vacancy, profile),
            matches_roles(vacancy, profile),
            matches_salary(vacancy, profile),
            matches_experience(vacancy, profile),
            matches_work_format(vacancy, profile),
            matches_city(vacancy, profile),
            matches_source(vacancy, profile),
            matches_age(vacancy, profile, now=now),
        ]
    )


def filter_vacancies(
    vacancies: list[Vacancy],
    profile: SearchProfile,
    now: datetime | None = None,
) -> list[Vacancy]:
    return [v for v in vacancies if vacancy_matches_profile(v, profile, now=now)]
