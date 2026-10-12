"""Telegram filter catalog + matching (mirrors Flutter vacancy filters)."""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import timedelta
from typing import Any

from app.core.timeutil import utc_now_naive

# ── 1. Область (роль) ──────────────────────────────────────────────
TELEGRAM_ROLES: list[tuple[str, str]] = [
    ("Backend", "Backend"),
    ("Frontend", "Frontend"),
    ("Fullstack", "Fullstack"),
    ("Mobile", "Mobile"),
    ("Android", "Android"),
    ("iOS", "iOS"),
    ("QA", "QA"),
    ("DevOps", "DevOps"),
    ("SRE", "SRE"),
    ("Data", "Data"),
    ("ML", "ML"),
    ("Analyst", "Анализ данных"),
    ("Architect", "Architect"),
    ("Manager", "Manager"),
    ("Embedded", "Embedded"),
    ("Security", "Security"),
]

# ── 2. Стек: языки ─────────────────────────────────────────────────
TELEGRAM_LANGUAGES: list[str] = [
    "Python",
    "Go",
    "Java",
    "JavaScript",
    "TypeScript",
    "Kotlin",
    "PHP",
    "C#",
    "C++",
    "Rust",
    "Ruby",
    "Swift",
    "Scala",
    "SQL",
]

# ── 2b. Стек: фреймворки / инструменты ─────────────────────────────
TELEGRAM_FRAMEWORKS: list[str] = [
    "React",
    "Vue",
    "Angular",
    "Next.js",
    "Nuxt",
    "Django",
    "FastAPI",
    "Flask",
    "Spring",
    "Node.js",
    "NestJS",
    "Express",
    "Flutter",
    "React Native",
    "Docker",
    "Kubernetes",
    "AWS",
    "GCP",
    "Azure",
    "PostgreSQL",
    "MySQL",
    "MongoDB",
    "Redis",
    "Kafka",
    "RabbitMQ",
    "Elasticsearch",
    "GraphQL",
    "gRPC",
    "TensorFlow",
    "PyTorch",
    "Spark",
    "Airflow",
    "dbt",
    "Pandas",
]

TELEGRAM_STACK: list[str] = TELEGRAM_LANGUAGES + TELEGRAM_FRAMEWORKS

# ── Формат / опыт / занятость / период ─────────────────────────────
TELEGRAM_WORK_FORMATS: list[tuple[str, str]] = [
    ("remote", "Удалёнка"),
    ("hybrid", "Гибрид"),
    ("office", "Офис"),
]

TELEGRAM_EXPERIENCES: list[tuple[str, str]] = [
    ("no_experience", "Без опыта"),
    ("between_1_and_3", "1–3 года"),
    ("between_3_and_6", "3–6 лет"),
    ("more_than_6", "6+ лет"),
]

TELEGRAM_EMPLOYMENT: list[tuple[str, str]] = [
    ("full", "Full"),
    ("part", "Part"),
    ("contract", "Contract"),
    ("intern", "Intern"),
]

TELEGRAM_AGE_HOURS: list[tuple[int, str]] = [
    (24, "сутки"),
    (72, "3 дня"),
    (168, "неделя"),
    (336, "2 недели"),
    (720, "месяц"),
]

# Период выгрузки при синке (как в настройках Flutter)
TELEGRAM_SYNC_LOOKBACK: list[tuple[int, str]] = [
    (1, "За сутки"),
    (3, "За 3 дня"),
    (7, "За неделю"),
    (14, "За 2 недели"),
    (30, "За месяц"),
]

TELEGRAM_SALARY_FROM: list[int] = [100_000, 150_000, 200_000, 250_000, 300_000, 400_000, 500_000]
TELEGRAM_SALARY_TO: list[int] = [150_000, 200_000, 250_000, 300_000, 400_000, 500_000, 700_000]

TELEGRAM_PORTALS: list[tuple[str, str]] = [
    ("hh", "hh.ru"),
    ("habr", "Habr"),
    ("hirify", "Hirify"),
    ("talanto", "Talanto"),
    ("getmatch", "GetMatch"),
    ("remoteok", "Remote OK"),
    ("remotive", "Remotive"),
    ("himalayas", "Himalayas"),
    ("jobicy", "Jobicy"),
    ("arbeitnow", "Arbeitnow"),
    ("weworkremotely", "WWR"),
    ("workingnomads", "Nomads"),
    ("greenhouse", "Careers"),
]

TELEGRAM_COMPANIES: list[tuple[str, str]] = [
    ("Avito", "Avito"),
    ("X5", "X5 Tech"),
    ("VK", "VK"),
    ("Райффайзен", "Raiffeisen"),
    ("Ozon", "Ozon"),
    ("Яндекс", "Яндекс"),
    ("Сбер", "Сбер"),
    ("HeadHunter", "hh.ru"),
    ("Wildberries", "Wildberries"),
    ("Т-Банк", "Т-Банк"),
    ("Альфа", "Альфа-Банк"),
    ("МТС", "МТС"),
    ("Контур", "Контур"),
    ("Мегафон", "Мегафон"),
    ("ВТБ", "ВТБ"),
    ("Kaspersky", "Kaspersky"),
    ("Lamoda", "Lamoda"),
    ("2ГИС", "2ГИС"),
]

TELEGRAM_CITIES: list[str] = [
    "Москва",
    "Санкт-Петербург",
    "Новосибирск",
    "Екатеринбург",
    "Казань",
    "Нижний Новгород",
    "Самара",
    "Краснодар",
    "Минск",
    "Алматы",
    "Remote",
]

DEFAULT_TELEGRAM_FILTERS: dict[str, Any] = {
    "roles": [],
    "skills": [],
    "work_formats": [],
    "experiences": [],
    "sources": [],
    "companies": [],
    "cities": [],
    "employment_types": [],
    "salary_from": None,
    "salary_to": None,
    "has_salary": None,
    "max_age_hours": None,
}


def empty_filters() -> dict[str, Any]:
    return deepcopy(DEFAULT_TELEGRAM_FILTERS)


def normalize_filters(raw: dict[str, Any] | None) -> dict[str, Any]:
    out = empty_filters()
    if not raw:
        return out
    for key in ("roles", "skills", "work_formats", "experiences", "sources", "companies", "cities", "employment_types"):
        val = raw.get(key)
        if isinstance(val, list):
            out[key] = [str(x) for x in val if x is not None and str(x).strip()]
    for key in ("salary_from", "salary_to", "max_age_hours"):
        val = raw.get(key)
        if val is None or val == "":
            out[key] = None
        else:
            try:
                out[key] = int(val)
            except (TypeError, ValueError):
                out[key] = None
    has_salary = raw.get("has_salary")
    if has_salary is True or has_salary is False:
        out["has_salary"] = has_salary
    elif has_salary in ("true", "1", 1):
        out["has_salary"] = True
    elif has_salary in ("false", "0", 0):
        out["has_salary"] = False
    else:
        out["has_salary"] = None
    return out


def load_filters_from_settings(app_settings: Any) -> dict[str, Any]:
    raw = getattr(app_settings, "telegram_filters", None)
    if isinstance(raw, dict) and raw:
        return normalize_filters(raw)
    # Fallback for pre-0006 rows
    merged = empty_filters()
    roles = getattr(app_settings, "telegram_roles", None) or []
    formats = getattr(app_settings, "telegram_work_formats", None) or []
    if roles:
        merged["roles"] = list(roles)
    if formats:
        merged["work_formats"] = list(formats)
    return merged


def save_filters_to_settings(app_settings: Any, filters: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_filters(filters)
    app_settings.telegram_filters = normalized
    # Keep legacy columns in sync for older readers
    app_settings.telegram_roles = list(normalized["roles"])
    app_settings.telegram_work_formats = list(normalized["work_formats"])
    return normalized


def filters_ready(filters: dict[str, Any]) -> bool:
    """
    Рассылка/browse если выбран хотя бы один «содержательный» критерий.
    Одна только свежесть (max_age_hours) не считается — иначе после синка
    матчились бы вообще все вакансии периода.
    """
    f = normalize_filters(filters)
    return any(
        [
            bool(f["roles"]),
            bool(f["skills"]),
            bool(f["work_formats"]),
            bool(f["experiences"]),
            bool(f["sources"]),
            bool(f["companies"]),
            bool(f["cities"]),
            bool(f["employment_types"]),
            f["salary_from"] is not None,
            f["salary_to"] is not None,
            f["has_salary"] is not None,
        ]
    )


def _blob(vacancy: Any) -> str:
    parts = [
        getattr(vacancy, "title", None) or "",
        getattr(vacancy, "description", None) or "",
        " ".join(getattr(vacancy, "skills", None) or []),
        getattr(vacancy, "company", None) or "",
    ]
    return " ".join(parts).lower()


def _label_map(pairs: list[tuple[str, str]]) -> dict[str, str]:
    return {k: v for k, v in pairs}


def format_filters_summary(
    filters: dict[str, Any],
    *,
    lookback_days: int | None = None,
) -> str:
    f = normalize_filters(filters)
    role_labels = _label_map(TELEGRAM_ROLES)
    fmt_labels = _label_map(TELEGRAM_WORK_FORMATS)
    exp_labels = _label_map(TELEGRAM_EXPERIENCES)
    portal_labels = _label_map(TELEGRAM_PORTALS)
    company_labels = {q: label for q, label in TELEGRAM_COMPANIES}
    empl_labels = _label_map(TELEGRAM_EMPLOYMENT)
    age_labels = {h: label for h, label in TELEGRAM_AGE_HOURS}

    def join_or(items: list[str], mapping: dict[str, str] | None = None, empty: str = "—") -> str:
        if not items:
            return empty
        if mapping:
            return ", ".join(mapping.get(x, x) for x in items)
        return ", ".join(items)

    langs = [s for s in f["skills"] if s in TELEGRAM_LANGUAGES]
    fws = [s for s in f["skills"] if s in TELEGRAM_FRAMEWORKS]
    other_skills = [s for s in f["skills"] if s not in TELEGRAM_LANGUAGES and s not in TELEGRAM_FRAMEWORKS]

    salary_bits: list[str] = []
    if f["salary_from"] is not None:
        salary_bits.append(f"от {f['salary_from']:,} ₽".replace(",", " "))
    if f["salary_to"] is not None:
        salary_bits.append(f"до {f['salary_to']:,} ₽".replace(",", " "))
    if f["has_salary"] is True:
        salary_bits.append("только с вилкой")
    elif f["has_salary"] is False:
        salary_bits.append("без вилки")
    salary_line = ", ".join(salary_bits) if salary_bits else "любая"

    age = f["max_age_hours"]
    age_line = age_labels.get(age, f"{age}ч") if age else "любой"

    lookback_labels = {d: label for d, label in TELEGRAM_SYNC_LOOKBACK}
    lookback_line = (
        lookback_labels.get(int(lookback_days), f"{lookback_days} дн.")
        if lookback_days
        else "—"
    )

    status = (
        "рассылка вкл"
        if filters_ready(f)
        else "выбери область/стек/… — иначе рассылка выкл"
    )

    return (
        f"<b>Фильтры Telegram</b> · {status}\n\n"
        f"1️⃣ Область: <b>{join_or(f['roles'], role_labels, '—')}</b>\n"
        f"2️⃣ Языки: <b>{join_or(langs, empty='—')}</b>\n"
        f"2️⃣ Фреймворки: <b>{join_or(fws + other_skills, empty='—')}</b>\n"
        f"Формат: <b>{join_or(f['work_formats'], fmt_labels, '—')}</b>\n"
        f"Опыт: <b>{join_or(f['experiences'], exp_labels, '—')}</b>\n"
        f"Зарплата: <b>{salary_line}</b>\n"
        f"Порталы: <b>{join_or(f['sources'], portal_labels, '—')}</b>\n"
        f"Компании: <b>{join_or(f['companies'], company_labels, '—')}</b>\n"
        f"Города: <b>{join_or(f['cities'], empty='—')}</b>\n"
        f"Занятость: <b>{join_or(f['employment_types'], empl_labels, '—')}</b>\n"
        f"Свежесть карточек: <b>{age_line}</b>\n"
        f"Выгрузка (синк): <b>{lookback_line}</b>\n\n"
        "Внутри группы — <b>OR</b> (Backend или Frontend). "
        "Между группами — <b>AND</b> (область и стек сразу). "
        "Роль смотрим только в <b>названии</b> вакансии.\n"
        "/filters · /browse · /sync · /stats · /test · /status · /reset"
    )


# Role → regexes applied to TITLE only (not description — иначе ML/AI
# с фразой "backend services" ложно проходят как Backend).
_ROLE_TITLE_PATTERNS: dict[str, tuple[str, ...]] = {
    "backend": (
        r"back[\s\-]?end",
        r"бэк[\s\-]?енд",
        r"бекенд",
        r"бэкендер",
    ),
    "frontend": (
        r"front[\s\-]?end",
        r"фронт[\s\-]?енд",
        r"фронтендер",
    ),
    "fullstack": (
        r"full[\s\-]?stack",
        r"фул[\s\-]?стек",
        r"фуллстек",
    ),
    "mobile": (r"mobile", r"мобильн"),
    "android": (r"android", r"андроид"),
    "ios": (r"\bios\b", r"iphone", r"swift"),
    "qa": (r"\bqa\b", r"тест[а-я]*", r"quality\s*assurance", r"sdet"),
    "devops": (r"devops", r"dev[\s\-]?ops", r"sre"),
    "sre": (r"\bsre\b", r"site\s*reliability"),
    "data": (
        r"data\s*engineer",
        r"data\s*platform",
        r"инженер\s*данн",
        r"данны[мх]",
        r"\betl\b",
        r"warehouse",
    ),
    "ml": (
        r"\bml\b",
        r"machine\s*learning",
        r"deep\s*learning",
        r"llm",
        r"нейросет",
        r"mlops",
    ),
    "analyst": (
        r"analyst",
        r"аналитик",
        r"analytics",
        r"аналитик[аеи]",
    ),
    "architect": (r"architect", r"архитектор"),
    "manager": (r"manager", r"менеджер", r"head\s+of", r"team\s*lead"),
    "embedded": (r"embedded", r"встраиваем"),
    "security": (r"security", r"безопасн", r"appsec", r"infosec"),
    "python": (r"python", r"питон"),
    "java": (r"\bjava\b"),
    "go": (r"\bgolang\b", r"\bgo\s+developer\b", r"go\-developer"),
}


def _match_roles(vacancy: Any, roles: list[str]) -> bool:
    """OR within roles; match title only."""
    title = (getattr(vacancy, "title", None) or "").lower()
    if not title:
        return False
    for role in roles:
        key = role.lower().strip()
        if not key:
            continue
        patterns = _ROLE_TITLE_PATTERNS.get(key)
        if patterns:
            if any(re.search(p, title, flags=re.IGNORECASE) for p in patterns):
                return True
            continue
        # Fallback: whole-word-ish substring in title
        if re.search(rf"(?<![a-zа-я0-9]){re.escape(key)}(?![a-zа-я0-9])", title, flags=re.I):
            return True
    return False


def _match_skills(vacancy: Any, skills: list[str]) -> bool:
    """OR within skills; title + skills + description."""
    blob = _blob(vacancy)
    return any(skill.lower().strip() in blob for skill in skills if skill.strip())


def _match_work_formats(vacancy: Any, formats: list[str]) -> bool:
    fmt = (getattr(vacancy, "work_format", None) or "unknown").lower()
    remote = bool(getattr(vacancy, "remote", False))
    allowed = {x.lower() for x in formats}
    if "remote" in allowed and (remote or fmt == "remote"):
        return True
    return fmt in allowed


def _match_experiences(vacancy: Any, experiences: list[str]) -> bool:
    exp = getattr(vacancy, "experience", None) or ""
    return exp in experiences


def _match_sources(vacancy: Any, sources: list[str]) -> bool:
    src = (getattr(vacancy, "source", None) or "").lower()
    return src in {s.lower() for s in sources}


def _match_companies(vacancy: Any, companies: list[str]) -> bool:
    company = (getattr(vacancy, "company", None) or "").lower()
    return any(c.lower() in company for c in companies)


def _match_cities(vacancy: Any, cities: list[str]) -> bool:
    city = (getattr(vacancy, "city", None) or "").lower()
    remote = bool(getattr(vacancy, "remote", False))
    fmt = (getattr(vacancy, "work_format", None) or "").lower()
    for c in cities:
        cl = c.lower()
        if cl in {"remote", "удалённо", "удаленно"} and (remote or fmt == "remote"):
            return True
        if cl in city:
            return True
    return False


def _match_employment(vacancy: Any, types: list[str]) -> bool:
    emp = (getattr(vacancy, "employment_type", None) or "").lower()
    return any(e.lower() in emp for e in types)


def _match_salary(vacancy: Any, *, salary_from: int | None, salary_to: int | None, has_salary: bool | None) -> bool:
    vac_from_raw = getattr(vacancy, "salary_from", None)
    vac_to_raw = getattr(vacancy, "salary_to", None)
    if has_salary is True and vac_from_raw is None and vac_to_raw is None:
        return False
    if has_salary is False and (vac_from_raw is not None or vac_to_raw is not None):
        return False
    if salary_from is None and salary_to is None and has_salary is None:
        return False
    if salary_from is None and salary_to is None:
        return has_salary is not None
    from app.services.currency import salary_in_rub

    vac_from, vac_to, _ = salary_in_rub(
        vac_from_raw,
        vac_to_raw,
        getattr(vacancy, "currency", None),
    )
    if vac_from is None and vac_to is None:
        return False
    if salary_from is not None:
        vac_max = vac_to if vac_to is not None else vac_from
        if vac_max is not None and vac_max < salary_from:
            return False
    if salary_to is not None:
        vac_min = vac_from if vac_from is not None else vac_to
        if vac_min is not None and vac_min > salary_to:
            return False
    return True


def _match_age(vacancy: Any, max_age_hours: int) -> bool:
    published = getattr(vacancy, "published_at", None)
    if published is None:
        return False
    cutoff = utc_now_naive() - timedelta(hours=int(max_age_hours))
    pub = published.replace(tzinfo=None) if getattr(published, "tzinfo", None) else published
    return pub >= cutoff


def vacancy_matches_telegram_filters(vacancy: Any, filters: dict[str, Any] | None = None, **legacy: Any) -> bool:
    """
    True if vacancy fits Telegram selections.

    - Inside a group (roles / skills / …): OR
    - Across groups: AND (все выбранные группы должны пройти)
    - Role matches TITLE only (не description)
    - max_age_hours / salary — уточняющие AND-ограничения
    """
    if getattr(vacancy, "removed_at", None) is not None:
        return False
    if filters is None:
        filters = {
            "roles": legacy.get("roles") or [],
            "work_formats": legacy.get("work_formats") or [],
            "skills": legacy.get("skills") or [],
        }
    f = normalize_filters(filters)
    if not filters_ready(f):
        return False

    if f["roles"] and not _match_roles(vacancy, f["roles"]):
        return False
    if f["skills"] and not _match_skills(vacancy, f["skills"]):
        return False
    if f["work_formats"] and not _match_work_formats(vacancy, f["work_formats"]):
        return False
    if f["experiences"] and not _match_experiences(vacancy, f["experiences"]):
        return False
    if f["sources"] and not _match_sources(vacancy, f["sources"]):
        return False
    if f["companies"] and not _match_companies(vacancy, f["companies"]):
        return False
    if f["cities"] and not _match_cities(vacancy, f["cities"]):
        return False
    if f["employment_types"] and not _match_employment(vacancy, f["employment_types"]):
        return False
    if f["salary_from"] is not None or f["salary_to"] is not None or f["has_salary"] is not None:
        if not _match_salary(
            vacancy,
            salary_from=f["salary_from"],
            salary_to=f["salary_to"],
            has_salary=f["has_salary"],
        ):
            return False
    if f["max_age_hours"] is not None and not _match_age(vacancy, f["max_age_hours"]):
        return False

    return True
