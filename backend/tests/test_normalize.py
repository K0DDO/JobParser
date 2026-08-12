from datetime import datetime

from app.schemas import VacancyData
from app.services.normalize import build_fingerprint, canonicalize_url, normalize_vacancy


def test_canonicalize_url_strips_utm():
    url = "https://hh.ru/vacancy/123?utm_source=x&utm_medium=y&from=main"
    assert canonicalize_url(url) == "https://hh.ru/vacancy/123"


def test_normalize_vacancy_swaps_salary_bounds():
    data = VacancyData(
        source="hh",
        source_vacancy_id="1",
        url="https://hh.ru/vacancy/1",
        title="  Dev  ",
        salary_from=300000,
        salary_to=200000,
        currency="rub",
        skills=[" Python ", "FastAPI", "Python"],
    )
    result = normalize_vacancy(data)
    assert result.salary_from == 200000
    assert result.salary_to == 300000
    assert result.currency == "RUB"
    assert result.skills == ["FastAPI", "Python"]
    assert result.title == "Dev"


def test_fingerprint_stable():
    a = VacancyData(
        source="hh",
        source_vacancy_id="1",
        url="https://hh.ru/vacancy/1",
        title="Python Dev",
        company="Acme",
        city="Moscow",
        salary_from=100,
        salary_to=200,
        currency="RUB",
    )
    b = VacancyData(
        source="hh",
        source_vacancy_id="999",
        url="https://other.ru/x",
        title="Python Dev",
        company="Acme",
        city="Moscow",
        salary_from=100,
        salary_to=200,
        currency="RUB",
    )
    assert build_fingerprint(a) == build_fingerprint(b)
