import pytest

from app.schemas import VacancyData
from app.services.normalize import build_fingerprint, canonicalize_url


def test_dedupe_priority_source_id_identity():
    a = VacancyData(
        source="hh",
        source_vacancy_id="42",
        url="https://hh.ru/vacancy/42",
        title="A",
        company="C",
    )
    b = VacancyData(
        source="hh",
        source_vacancy_id="42",
        url="https://hh.ru/vacancy/42?utm_source=x",
        title="A updated",
        company="C",
    )
    assert a.source == b.source
    assert a.source_vacancy_id == b.source_vacancy_id
    assert canonicalize_url(a.url) == canonicalize_url(b.url)


def test_fingerprint_differs_for_different_companies():
    a = VacancyData(
        source="hh",
        source_vacancy_id="1",
        url="https://hh.ru/vacancy/1",
        title="Dev",
        company="A",
        city="Moscow",
        salary_from=100,
        currency="RUB",
    )
    b = VacancyData(
        source="hh",
        source_vacancy_id="2",
        url="https://hh.ru/vacancy/2",
        title="Dev",
        company="B",
        city="Moscow",
        salary_from=100,
        currency="RUB",
    )
    assert build_fingerprint(a) != build_fingerprint(b)
