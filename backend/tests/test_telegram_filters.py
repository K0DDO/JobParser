from datetime import datetime, timedelta
from types import SimpleNamespace

from app.services.telegram_filters import (
    empty_filters,
    filters_ready,
    normalize_filters,
    vacancy_matches_telegram_filters,
)


def _vac(**kwargs):
    base = dict(
        title="Senior Backend Python Engineer",
        description="FastAPI Postgres Redis",
        skills=["Python", "FastAPI", "PostgreSQL"],
        company="Яндекс",
        source="hh",
        city="Москва",
        remote=True,
        work_format="remote",
        experience="between_1_and_3",
        employment_type="full",
        salary_from=250000,
        salary_to=350000,
        currency="RUB",
        published_at=datetime.utcnow(),
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_no_roles_means_not_ready():
    f = empty_filters()
    assert filters_ready(f) is False
    assert vacancy_matches_telegram_filters(_vac(), f) is False


def test_role_and_stack():
    f = normalize_filters({"roles": ["Backend"], "skills": ["Python", "FastAPI"]})
    assert vacancy_matches_telegram_filters(_vac(), f) is True
    assert vacancy_matches_telegram_filters(_vac(skills=["Java"], title="Backend Java"), f) is False


def test_analyst_alias():
    f = normalize_filters({"roles": ["Analyst"]})
    assert vacancy_matches_telegram_filters(
        _vac(title="Аналитик данных", skills=["SQL"], description="дашборды"),
        f,
    )


def test_work_format_and_salary():
    f = normalize_filters(
        {
            "roles": ["Backend"],
            "work_formats": ["office"],
            "salary_from": 200000,
        }
    )
    assert vacancy_matches_telegram_filters(_vac(), f) is False
    f["work_formats"] = ["remote"]
    assert vacancy_matches_telegram_filters(_vac(), f) is True


def test_age_filter():
    f = normalize_filters({"roles": ["Backend"], "max_age_hours": 24})
    old = _vac(published_at=datetime.utcnow() - timedelta(days=5))
    assert vacancy_matches_telegram_filters(old, f) is False
    assert vacancy_matches_telegram_filters(_vac(), f) is True


def test_company_and_portal():
    f = normalize_filters({"roles": ["Backend"], "companies": ["Яндекс"], "sources": ["hh"]})
    assert vacancy_matches_telegram_filters(_vac(), f) is True
    assert vacancy_matches_telegram_filters(_vac(company="Ozon"), f) is False
