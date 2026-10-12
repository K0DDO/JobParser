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


def test_age_alone_not_ready():
    f = normalize_filters({"max_age_hours": 168})
    assert filters_ready(f) is False


def test_and_across_role_and_skill():
    f = normalize_filters({"roles": ["Backend"], "skills": ["Python"]})
    assert vacancy_matches_telegram_filters(_vac(), f) is True
    assert (
        vacancy_matches_telegram_filters(
            _vac(title="Backend Java", skills=["Java"], description="Spring"),
            f,
        )
        is False
    )


def test_or_within_roles():
    f = normalize_filters({"roles": ["Backend", "Frontend"]})
    assert vacancy_matches_telegram_filters(_vac(title="Frontend React"), f) is True
    assert vacancy_matches_telegram_filters(_vac(title="Go Developer"), f) is False


def test_backend_ignores_ml_even_if_description_mentions_backend():
    f = normalize_filters({"roles": ["Backend"]})
    assert (
        vacancy_matches_telegram_filters(
            _vac(
                title="AI Platform Engineer",
                skills=[
                    "AI-ML-Platform-Engineer",
                    "Machine-Learning-Platform-Engineer",
                ],
                description="Collaborate with backend teams on platform APIs",
            ),
            f,
        )
        is False
    )


def test_skill_only_ready():
    f = normalize_filters({"skills": ["FastAPI"]})
    assert filters_ready(f) is True
    assert vacancy_matches_telegram_filters(_vac(), f) is True


def test_analyst_alias_in_title():
    f = normalize_filters({"roles": ["Analyst"]})
    assert vacancy_matches_telegram_filters(
        _vac(title="Аналитик данных", skills=["SQL"], description="дашборды"),
        f,
    )


def test_work_format_and_role():
    f = normalize_filters({"roles": ["Backend"], "work_formats": ["office"]})
    assert vacancy_matches_telegram_filters(_vac(), f) is False
    assert (
        vacancy_matches_telegram_filters(_vac(work_format="office", remote=False), f)
        is True
    )


def test_removed_never_matches():
    f = normalize_filters({"roles": ["Backend"]})
    assert vacancy_matches_telegram_filters(_vac(removed_at=datetime.utcnow()), f) is False


def test_company_and_portal():
    f = normalize_filters({"companies": ["Яндекс"], "sources": ["habr"]})
    assert vacancy_matches_telegram_filters(_vac(), f) is False
    assert vacancy_matches_telegram_filters(_vac(source="habr"), f) is True


def test_age_as_constraint_with_role():
    f = normalize_filters({"roles": ["Backend"], "max_age_hours": 24})
    old = _vac(published_at=datetime.utcnow() - timedelta(days=5))
    assert vacancy_matches_telegram_filters(old, f) is False
    assert vacancy_matches_telegram_filters(_vac(), f) is True
