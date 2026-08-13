from app.schemas import VacancyData
from app.services.normalize import (
    build_fingerprint,
    canonicalize_url,
    detect_hours_per_day,
    normalize_vacancy,
    parse_iso_datetime,
    to_monthly_amount,
)


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


def test_normalize_vacancy_clips_long_city():
    loc = (
        "Boston, Massachusetts, USA; Connecticut, USA; Remote; Delaware, USA; Remote; "
        "District of Columbia, USA; Remote; Maryland, USA; Remote; Massachusetts, USA; Remote; "
        "New Jersey, USA; Remote; New York, New York, USA; New York, USA; Remote; Rhode Island, USA; Remote"
    )
    data = VacancyData(
        source="greenhouse",
        source_vacancy_id="7777798",
        url="https://careers.datadoghq.com/detail/7777798/?gh_jid=7777798",
        title="Staff Application Security Engineer",
        company="Datadog",
        city=loc,
    )
    result = normalize_vacancy(data)
    assert result.city == "Boston, Massachusetts, USA"
    assert len(result.city) <= 256


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


def test_hourly_salary_converts_to_monthly_8h_22d():
    data = VacancyData(
        source="remotive",
        source_vacancy_id="h1",
        url="https://example.com/1",
        title="Python Dev",
        description="Rate $50/hr, full-time remote",
        salary_from=50,
        salary_to=70,
        currency="USD",
        salary_period="hourly",
    )
    result = normalize_vacancy(data)
    assert result.salary_from == 50 * 8 * 22
    assert result.salary_to == 70 * 8 * 22
    assert result.salary_period == "monthly"


def test_hourly_respects_stated_hours_per_day():
    data = VacancyData(
        source="remotive",
        source_vacancy_id="h2",
        url="https://example.com/2",
        title="Support",
        description="Part-time 4 hours a day, 20 USD per hour",
        salary_from=20,
        currency="USD",
        salary_period="hourly",
    )
    result = normalize_vacancy(data)
    assert detect_hours_per_day(data.description) == 4
    assert result.salary_from == 20 * 4 * 22


def test_yearly_salary_divides_to_monthly():
    data = VacancyData(
        source="remoteok",
        source_vacancy_id="y1",
        url="https://example.com/3",
        title="Backend",
        salary_from=120000,
        salary_to=180000,
        currency="USD",
        salary_period="yearly",
    )
    result = normalize_vacancy(data)
    assert result.salary_from == 10000
    assert result.salary_to == 15000


def test_rub_monthly_salary_stays():
    data = VacancyData(
        source="hh",
        source_vacancy_id="m1",
        url="https://hh.ru/vacancy/1",
        title="Python",
        salary_from=200000,
        salary_to=300000,
        currency="RUB",
        salary_period="monthly",
    )
    result = normalize_vacancy(data)
    assert result.salary_from == 200000
    assert result.salary_to == 300000


def test_parse_iso_datetime_accepts_unix_ts():
    dt = parse_iso_datetime(1700000000)
    assert dt is not None
    assert dt.year == 2023


def test_to_monthly_amount_helpers():
    assert to_monthly_amount(50, "hourly") == 8800
    assert to_monthly_amount(400, "daily") == 8800
    assert to_monthly_amount(1200, "weekly") == 5200
    assert to_monthly_amount(120000, "yearly") == 10000
    assert to_monthly_amount(180000, "monthly") == 180000


def test_himalayas_annual_usd_becomes_monthly():
    data = VacancyData(
        source="himalayas",
        source_vacancy_id="nv",
        url="https://himalayas.app/jobs/1",
        title="Senior Full-Stack Software Engineer",
        company="NVIDIA",
        salary_from=224000,
        salary_to=356500,
        currency="USD",
        salary_period="annual",
    )
    result = normalize_vacancy(data)
    assert result.salary_from == 18667
    assert result.salary_to == 29708


def test_mislabeled_monthly_high_usd_treated_as_yearly():
    data = VacancyData(
        source="himalayas",
        source_vacancy_id="x",
        url="https://example.com/2",
        title="Director",
        salary_from=150000,
        salary_to=185000,
        currency="USD",
        salary_period="monthly",
    )
    result = normalize_vacancy(data)
    assert result.salary_from == 12500
    assert result.salary_to == 15417


def test_remotive_slash_hour_and_k_suffix():
    hourly = VacancyData(
        source="remotive",
        source_vacancy_id="h",
        url="https://example.com/h",
        title="AI Engineer",
        salary_from=90,
        salary_to=150,
        currency="USD",
        raw_data={"salary": "$90 - $150 /hour"},
    )
    hourly = normalize_vacancy(hourly)
    assert hourly.salary_from == 90 * 8 * 22
    assert hourly.salary_to == 150 * 8 * 22

    yearly_k = VacancyData(
        source="remotive",
        source_vacancy_id="k",
        url="https://example.com/k",
        title="Copywriter",
        salary_from=20000,
        salary_to=35000,
        currency="USD",
        raw_data={"salary": "$20k -$35k"},
    )
    yearly_k = normalize_vacancy(yearly_k)
    assert yearly_k.salary_from == 1667
    assert yearly_k.salary_to == 2917


def test_getmatch_usd_monthly_stays():
    data = VacancyData(
        source="getmatch",
        source_vacancy_id="gm",
        url="https://getmatch.ru/vacancies/1",
        title="Senior AI Software Engineer",
        salary_from=20000,
        salary_to=30000,
        currency="USD",
        salary_period="monthly",
    )
    result = normalize_vacancy(data)
    assert result.salary_from == 20000
    assert result.salary_to == 30000
