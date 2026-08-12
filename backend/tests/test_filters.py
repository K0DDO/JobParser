from datetime import datetime, timedelta

from app.models import SearchProfile, Vacancy
from app.services.filters import (
    matches_age,
    matches_experience,
    matches_salary,
    matches_skills,
    matches_source,
    matches_work_format,
    vacancy_matches_profile,
)
from app.services.vacancies import build_vacancy_filters


def _vacancy(**kwargs) -> Vacancy:
    defaults = {
        "source": "hh",
        "source_vacancy_id": "1",
        "url": "https://hh.ru/vacancy/1",
        "title": "Python Backend Developer",
        "company": "Acme",
        "description": "Work with FastAPI and PostgreSQL",
        "salary_from": 200000,
        "salary_to": 300000,
        "currency": "RUB",
        "city": "Москва",
        "remote": True,
        "work_format": "remote",
        "experience": "between_1_and_3",
        "skills": ["Python", "FastAPI"],
        "status": "new",
        "published_at": datetime.utcnow(),
    }
    defaults.update(kwargs)
    return Vacancy(**defaults)


def _profile(**kwargs) -> SearchProfile:
    defaults = {
        "name": "Python Backend",
        "is_active": True,
        "include_skills": ["Python"],
        "exclude_skills": ["PHP"],
        "roles": ["Backend"],
        "salary_from": 180000,
        "currency": "RUB",
        "experience_levels": ["between_1_and_3"],
        "work_formats": ["remote"],
        "cities": ["Москва"],
        "sources": ["hh"],
        "max_age_hours": 72,
    }
    defaults.update(kwargs)
    return SearchProfile(**defaults)


def test_skills_include_and_exclude():
    v = _vacancy()
    p = _profile()
    assert matches_skills(v, p) is True
    p.exclude_skills = ["FastAPI"]
    assert matches_skills(v, p) is False


def test_salary_filtering():
    v = _vacancy(salary_from=100000, salary_to=150000)
    p = _profile(salary_from=180000)
    assert matches_salary(v, p) is False

    v2 = _vacancy(salary_from=200000, salary_to=250000)
    assert matches_salary(v2, p) is True


def test_experience_filtering():
    v = _vacancy(experience="more_than_6")
    p = _profile(experience_levels=["between_1_and_3"])
    assert matches_experience(v, p) is False


def test_source_filtering():
    v = _vacancy(source="habr")
    p = _profile(sources=["hh"])
    assert matches_source(v, p) is False


def test_work_format_filtering():
    v = _vacancy(work_format="office", remote=False)
    p = _profile(work_formats=["remote"])
    assert matches_work_format(v, p) is False


def test_age_filtering():
    v = _vacancy(published_at=datetime.utcnow() - timedelta(hours=100))
    p = _profile(max_age_hours=24)
    assert matches_age(v, p) is False


def test_full_profile_match():
    v = _vacancy()
    p = _profile()
    assert vacancy_matches_profile(v, p) is True


def test_inactive_profile_never_matches():
    v = _vacancy()
    p = _profile(is_active=False)
    assert vacancy_matches_profile(v, p) is False


def test_feed_filters_cover_core_dimensions():
    clauses = build_vacancy_filters(
        source="habr,hirify",
        status="matched,new",
        q="fastapi",
        city="Москва,СПб",
        work_format="remote,hybrid",
        experience="between_1_and_3,between_3_and_6",
        salary_from=180000,
        salary_to=400000,
        currency="RUB",
        skill="Python,Go",
        role="Backend,Frontend",
        company="Acme",
        max_age_hours=24,
        has_salary=True,
        employment_type="full,part",
    )
    assert len(clauses) == 14


def test_feed_filters_accept_lists():
    clauses = build_vacancy_filters(
        source=["habr", "getmatch"],
        experience=["no_experience", "more_than_6"],
        skill=["Python"],
    )
    assert len(clauses) == 3
