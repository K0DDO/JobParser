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
        removed_at=None,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_empty_filters_not_ready():
    f = empty_filters()
    assert filters_ready(f) is False
    assert vacancy_matches_telegram_filters(_vac(), f) is False


def test_union_role_or_skill():
    """Backend OR Python — Java Backend matches via role even without Python."""
    f = normalize_filters({"roles": ["Backend"], "skills": ["Python"]})
    assert vacancy_matches_telegram_filters(_vac(), f) is True
    assert vacancy_matches_telegram_filters(
        _vac(title="Backend Java", skills=["Java"], description="Spring"),
        f,
    ) is True
    assert vacancy_matches_telegram_filters(
        _vac(title="Data Analyst", skills=["SQL"], description="дашборды"),
        f,
    ) is False


def test_skill_only_ready():
    f = normalize_filters({"skills": ["FastAPI"]})
    assert filters_ready(f) is True
    assert vacancy_matches_telegram_filters(_vac(), f) is True


def test_analyst_alias():
    f = normalize_filters({"roles": ["Analyst"]})
    assert vacancy_matches_telegram_filters(
        _vac(title="Аналитик данных", skills=["SQL"], description="дашборды"),
        f,
    )


def test_work_format_alone():
    f = normalize_filters({"work_formats": ["office"]})
    assert vacancy_matches_telegram_filters(_vac(), f) is False
    assert vacancy_matches_telegram_filters(_vac(work_format="office", remote=False), f) is True


def test_union_format_or_role():
    f = normalize_filters({"roles": ["Backend"], "work_formats": ["office"]})
    # remote Backend still matches via role (OR, not AND)
    assert vacancy_matches_telegram_filters(_vac(), f) is True


def test_removed_never_matches():
    f = normalize_filters({"roles": ["Backend"]})
    assert vacancy_matches_telegram_filters(_vac(removed_at=datetime.utcnow()), f) is False


def test_company_or_portal():
    f = normalize_filters({"companies": ["Яндекс"], "sources": ["habr"]})
    # hh + Яндекс → company matches
    assert vacancy_matches_telegram_filters(_vac(), f) is True
    # hh + Ozon → neither company nor portal
    assert vacancy_matches_telegram_filters(_vac(company="Ozon"), f) is False
    # habr + Ozon → source matches
    assert vacancy_matches_telegram_filters(_vac(company="Ozon", source="habr"), f) is True


def test_age_clause():
    f = normalize_filters({"max_age_hours": 24})
    old = _vac(published_at=datetime.utcnow() - timedelta(days=5))
    assert vacancy_matches_telegram_filters(old, f) is False
    assert vacancy_matches_telegram_filters(_vac(), f) is True
