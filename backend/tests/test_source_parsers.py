from app.core.enums import ExperienceLevel, WorkFormat
from app.parsers.getmatch import filter_sitemap_urls, normalize_getmatch_offer, parse_getmatch_page
from app.parsers.hirify import normalize_hirify_item
from app.parsers.talanto import normalize_talanto_item


def test_hirify_normalize_remote_and_skills():
    item = {
        "id": 1,
        "slug": "1-python-backend",
        "title": "Python Backend",
        "company_title": "Acme",
        "work_format": ["remote"],
        "remote_type": "world",
        "work_type": "fulltime",
        "created_at": "2026-08-12T10:00:00.000000Z",
        "tags": [{"name": "python"}, {"name": "fastapi"}],
        "grades": [{"name": "middle"}],
        "regions": [{"name": "Россия"}],
        "salary": {"from": 200000, "to": 300000, "currency": "RUB"},
        "tldr": "Build APIs",
    }
    data = normalize_hirify_item(item)
    assert data.source == "hirify"
    assert data.url.endswith("/jobs/1-python-backend")
    assert data.remote is True
    assert data.work_format == WorkFormat.REMOTE
    assert data.experience == ExperienceLevel.BETWEEN_1_AND_3
    assert "python" in data.skills
    assert data.salary_from == 200000


def test_talanto_normalize():
    item = {
        "id": "abc",
        "title": "Python Engineer",
        "company": "Canonical",
        "location": "Home based - EMEA",
        "remote_type": "remote",
        "level": "senior",
        "salary_min": 1000,
        "salary_max": 2000,
        "salary_currency": "USD",
        "published_at": "2024-11-15T16:12:02Z",
        "skills": ["Python"],
    }
    data = normalize_talanto_item(item)
    assert data.source == "talanto"
    assert data.remote is True
    assert data.experience == ExperienceLevel.BETWEEN_3_AND_6
    assert data.currency == "USD"
    assert data.url.endswith("/jobs/abc")


def test_getmatch_sitemap_filter_and_jsonld():
    xml = """
    <url><loc>https://getmatch.ru/vacancies/1-java-developer</loc></url>
    <url><loc>https://getmatch.ru/vacancies/2-python-backend</loc></url>
    <url><loc>https://getmatch.ru/vacancies/9-python-lead</loc></url>
    <url><loc>https://getmatch.ru/vacancies/3-ios-developer</loc></url>
    """
    urls = filter_sitemap_urls(xml, "Python Backend", 10)
    assert urls[0] == "https://getmatch.ru/vacancies/9-python-lead"
    assert "https://getmatch.ru/vacancies/2-python-backend" in urls

    html = """
    <meta property="og:description" content="Вакансия Python Backend, работа в компании Acme, полная удалёнка. Локации: Москва. Зарплата: 180 000 — 250 000 ₽/мес на руки.">
    <script type="application/ld+json">{"@type":"BreadcrumbList","itemListElement":[]}</script>
    <script type="application/ld+json">{"@type":"JobPosting","title":"Python Backend","hiringOrganization":{"name":"Acme"},"baseSalary":{"currency":"RUB","value":{"minValue":180000,"maxValue":250000}},"employmentType":"FULL_TIME","datePosted":"2026-07-23T04:25:46.591551"}</script>
    """
    data = parse_getmatch_page("https://getmatch.ru/vacancies/2-python-backend", html)
    assert data is not None
    assert data.company == "Acme"
    assert data.remote is True
    assert data.city == "Москва"
    assert data.salary_from == 180000
    assert data.salary_to == 250000


def test_getmatch_og_fallback_without_jobposting():
    html = """
    <meta property="og:title" content="Python разработчик — getmatch">
    <meta property="og:description" content="Вакансия Python разработчик, работа в компании Gigadata, полная удалёнка. Локации: Remote. Зарплата: 200 000 — 300 000 ₽/мес на руки.">
    <script type="application/ld+json">{"@type":"BreadcrumbList"}</script>
    """
    data = parse_getmatch_page("https://getmatch.ru/vacancies/35404-python-razrabotchik", html)
    assert data is not None
    assert data.title == "Python разработчик"
    assert data.company == "Gigadata"
    assert data.salary_from == 200000
    assert data.salary_to == 300000
    assert data.remote is True


def test_getmatch_offers_normalize():
    item = {
        "id": 35202,
        "position": "Python Backend",
        "url": "/vacancies/35202-python-backend",
        "published_at": "2026-08-04T11:04:38.811736",
        "salary_display_from": 180000,
        "salary_display_to": 250000,
        "salary_currency": "RUB",
        "offer_description": "Build APIs",
        "skills_objects": [{"name": "Python"}, {"name": "FastAPI"}],
        "location_items": [{"label": "Remote", "format": "remote", "exclude": False}],
        "company": {"name": "Acme"},
        "offer_type": "one_day_offer_v3",
    }
    data = normalize_getmatch_offer(item)
    assert data.source == "getmatch"
    assert data.url.endswith("/vacancies/35202-python-backend")
    assert data.company == "Acme"
    assert data.remote is True
    assert data.work_format == WorkFormat.REMOTE
    assert data.salary_from == 180000
    assert data.salary_to == 250000
    assert "Python" in data.skills


def test_remoteok_normalize_skips_legal_banner():
    from app.parsers.remoteok import normalize_remoteok_item

    assert normalize_remoteok_item({"legal": "terms"}) is None
    data = normalize_remoteok_item(
        {
            "id": "99",
            "slug": "remote-python-99",
            "position": "Python Dev",
            "company": "Acme",
            "tags": ["python", "backend"],
            "epoch": 1700000000,
            "url": "https://remoteok.com/remote-jobs/remote-python-99",
        }
    )
    assert data is not None
    assert data.source == "remoteok"
    assert data.remote is True
    assert "python" in data.skills


def test_himalayas_normalize():
    from app.parsers.himalayas import normalize_himalayas_item

    data = normalize_himalayas_item(
        {
            "title": "Python Developer",
            "companyName": "Hitapps",
            "applicationLink": "https://himalayas.app/companies/hitapps/jobs/python-developer",
            "minSalary": 5000,
            "maxSalary": 6500,
            "salaryPeriod": "monthly",
            "currency": "USD",
            "seniority": ["Senior"],
            "categories": ["Python-Development"],
            "locationRestrictions": [],
            "pubDate": 1700000000,
            "employmentType": "Full Time",
        }
    )
    assert data.source == "himalayas"
    assert data.salary_from == 5000
    assert data.salary_period == "monthly"
    assert data.experience == ExperienceLevel.BETWEEN_3_AND_6


def test_jobicy_accepts_list_job_type():
    from app.parsers.jobicy import normalize_jobicy_item

    data = normalize_jobicy_item(
        {
            "id": 42,
            "jobSlug": "python-dev",
            "jobTitle": "Python Dev",
            "companyName": "Acme",
            "jobGeo": "Remote",
            "jobType": ["Full-Time", "Contract"],
            "jobIndustry": ["Software Engineering"],
            "pubDate": 1700000000,
        }
    )
    assert data.employment_type == "Full-Time"
    assert "Software Engineering" in data.skills


def test_workingnomads_normalize_yearly_and_hourly():
    from app.parsers.workingnomads import normalize_workingnomads_item
    from app.services.normalize import normalize_vacancy

    yearly = normalize_workingnomads_item(
        {
            "id": 1789464,
            "slug": "associate-infrastructure-engineer-webflow",
            "title": "Associate Infrastructure Engineer",
            "company": "Webflow",
            "category_name": "Development",
            "position_type": "ft",
            "experience_level": "MID_LEVEL",
            "tags": ["python", "aws"],
            "locations": ["USA", "Canada"],
            "location_base": "USA,Canada",
            "pub_date": "2026-08-13T00:32:25.523477-04:00",
            "apply_url": "https://webflow.com/careers/infra",
            "annual_salary_usd": 190000,
            "salary_range": "$140k-$190k per year",
        }
    )
    assert yearly is not None
    assert yearly.source == "workingnomads"
    assert yearly.remote is True
    assert yearly.company == "Webflow"
    assert yearly.employment_type == "Full-time"
    assert yearly.experience == ExperienceLevel.BETWEEN_1_AND_3
    monthly = normalize_vacancy(yearly)
    assert monthly.salary_from == 11667
    assert monthly.salary_to == 15833
    assert monthly.salary_period == "monthly"

    hourly = normalize_workingnomads_item(
        {
            "id": 42,
            "slug": "housing-support",
            "title": "Housing Support Specialist",
            "company": "Sedgwick",
            "position_type": "pt",
            "experience_level": "SENIOR_LEVEL",
            "salary_range": "$17 per hour",
            "annual_salary_usd": 35360,
            "location_base": "USA",
        }
    )
    assert hourly is not None
    converted = normalize_vacancy(hourly)
    assert converted.salary_from == 17 * 8 * 22
    assert converted.experience == ExperienceLevel.BETWEEN_3_AND_6


def test_greenhouse_normalize():
    from app.parsers.greenhouse import normalize_greenhouse

    data = normalize_greenhouse(
        "GitLab",
        {
            "id": 123,
            "title": "Backend Engineer",
            "absolute_url": "https://job-boards.greenhouse.io/gitlab/jobs/123",
            "location": {"name": "Remote"},
            "updated_at": "2026-08-10T16:52:46-04:00",
            "company_name": "GitLab",
        },
    )
    assert data.source == "greenhouse"
    assert data.remote is True
    assert data.company == "GitLab"
