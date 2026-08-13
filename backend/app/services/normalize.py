import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from app.core.enums import ExperienceLevel, WorkFormat
from app.schemas import VacancyData


def canonicalize_url(url: str) -> str:
    """Strip tracking params and normalize URL for deduplication."""
    parsed = urlparse(url.strip())
    query = parse_qs(parsed.query, keep_blank_values=False)
    drop = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "from", "hhtmFrom"}
    cleaned = {k: v for k, v in query.items() if k.lower() not in drop}
    new_query = urlencode({k: v[0] for k, v in cleaned.items()}, doseq=False)
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", new_query, ""))


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    text = value.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def build_fingerprint(data: VacancyData) -> str:
    parts = [
        normalize_text(data.company),
        normalize_text(data.title),
        normalize_text(data.city),
        str(data.salary_from or ""),
        str(data.salary_to or ""),
        normalize_text(data.currency),
        normalize_text(data.source),
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _clip(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)].rstrip() + "…"


def compact_city(value: str | None) -> str | None:
    """Greenhouse etc. send multi-location blobs; keep a short filter-friendly city."""
    if not value:
        return None
    text = re.sub(r"\s+", " ", str(value).strip())
    for sep in (";", " | ", "|", " / ", "\n"):
        if sep in text:
            text = text.split(sep, 1)[0].strip()
            break
    text = re.sub(r",\s*Remote\s*$", "", text, flags=re.I).strip(" ,")
    return text or None


DEFAULT_HOURS_PER_DAY = 8
WORKING_DAYS_PER_MONTH = 22  # 8×22 = 176 hours / month

_PERIOD_ALIASES = {
    "hour": "hourly",
    "hourly": "hourly",
    "hr": "hourly",
    "per_hour": "hourly",
    "per-hour": "hourly",
    "час": "hourly",
    "day": "daily",
    "daily": "daily",
    "per_day": "daily",
    "per-day": "daily",
    "день": "daily",
    "week": "weekly",
    "weekly": "weekly",
    "per_week": "weekly",
    "недел": "weekly",
    "month": "monthly",
    "monthly": "monthly",
    "per_month": "monthly",
    "месяц": "monthly",
    "year": "yearly",
    "yearly": "yearly",
    "annual": "yearly",
    "annually": "yearly",
    "annum": "yearly",
    "per_year": "yearly",
    "год": "yearly",
}

# Foreign monthly senior can reach ~$15–35k; above this is almost always annual.
_YEARLY_FLOOR = {
    "USD": 40_000,
    "EUR": 36_000,
    "GBP": 32_000,
    "CAD": 50_000,
    "AUD": 50_000,
    "CHF": 40_000,
    "SGD": 50_000,
    "NZD": 50_000,
    "PLN": 80_000,
    "RUB": 900_000,
    "RUR": 900_000,
}


def detect_hours_per_day(text: str | None) -> int:
    if not text:
        return DEFAULT_HOURS_PER_DAY
    blob = text.lower()
    patterns = [
        r"(\d{1,2})\s*(?:hours?|hrs?|ч(?:аса|асов|ас)?)\s*(?:/|per|a|в)?\s*(?:day|день|сутк)",
        r"(\d{1,2})\s*h\s*/\s*d(?:ay)?",
        r"(\d{1,2})\s*ч\s*/\s*д",
    ]
    for pattern in patterns:
        match = re.search(pattern, blob)
        if match:
            hours = int(match.group(1))
            if 1 <= hours <= 16:
                return hours
    return DEFAULT_HOURS_PER_DAY


def magnitude_salary_period(amount: int | None, currency: str | None) -> str:
    amount = int(amount or 0)
    if amount <= 0:
        return "monthly"
    cur = (currency or "USD").upper()
    if cur in {"RUB", "RUR"}:
        if amount < 5_000:
            return "hourly"
        if amount >= _YEARLY_FLOOR["RUB"]:
            return "yearly"
        return "monthly"
    if amount < 80:
        return "hourly"
    if amount >= _YEARLY_FLOOR.get(cur, 40_000):
        return "yearly"
    return "monthly"


def detect_salary_period(
    text: str | None,
    amount: int | None,
    currency: str | None,
    explicit: str | None = None,
    salary_text: str | None = None,
) -> str:
    period = None
    if explicit:
        key = explicit.lower().strip().replace(" ", "_")
        for alias, mapped in sorted(_PERIOD_ALIASES.items(), key=lambda item: -len(item[0])):
            if alias in key:
                period = mapped
                break
    blob = (text or "").lower()
    if period is None:
        hint_groups = [
            (r"/hr\b|/hours?\b|\bhourly\b|per hour|an hour|в час|\$/h\b|€/h|£/h|час\.?\b", "hourly"),
            (r"/day\b|\bdaily\b|per day|в день|за день", "daily"),
            (r"/week\b|\bweekly\b|per week|в неделю", "weekly"),
            (
                r"/year\b|/yr\b|\byearly\b|\bannual|\bannum|per year|в год|за год|\bpa\b|\bp\.a\.?\b",
                "yearly",
            ),
            (r"/month\b|\bmonthly\b|per month|в месяц|за месяц|/mo\b", "monthly"),
        ]
        for pattern, mapped in hint_groups:
            if re.search(pattern, blob):
                period = mapped
                break
    extra = (salary_text or "").lower()
    if extra and (period is None or period == "monthly"):
        if re.search(r"\d+(?:[.,]\d+)?\s*k\b", extra) and not re.search(
            r"/hr\b|/hours?\b|\bhourly\b|per hour", extra
        ):
            period = "yearly"
    mag = magnitude_salary_period(amount, currency)
    if period is None:
        return mag
    # Himalayas etc. sometimes label annual USD figures as monthly.
    if period == "monthly" and mag == "yearly":
        return "yearly"
    if period == "hourly" and mag == "yearly":
        return "yearly"
    if period == "yearly" and mag == "hourly":
        return "monthly"
    return period


def to_monthly_amount(amount: int | None, period: str, hours_per_day: int = DEFAULT_HOURS_PER_DAY) -> int | None:
    if amount is None:
        return None
    hours = max(1, min(int(hours_per_day or DEFAULT_HOURS_PER_DAY), 16))
    if period == "hourly":
        return int(round(amount * hours * WORKING_DAYS_PER_MONTH))
    if period == "daily":
        return int(round(amount * WORKING_DAYS_PER_MONTH))
    if period == "weekly":
        return int(round(amount * 52 / 12))
    if period == "yearly":
        return int(round(amount / 12))
    return int(amount)


def normalize_vacancy(data: VacancyData) -> VacancyData:
    """Apply shared normalization rules to a vacancy payload."""
    data.source = _clip((data.source or "").strip(), 32) or "unknown"
    data.source_vacancy_id = _clip((data.source_vacancy_id or "").strip(), 128) or "unknown"
    data.title = _clip((data.title or "").strip() or "Untitled", 512) or "Untitled"
    data.company = _clip((data.company or "").strip() or None, 512)
    data.city = _clip(compact_city(data.city), 256)
    data.url = (data.url or "").strip()
    data.work_format = _clip((data.work_format or "unknown").strip(), 32) or "unknown"
    emp = data.employment_type
    if isinstance(emp, list):
        emp = next((x for x in emp if x), None)
    data.employment_type = _clip(str(emp).strip() if emp else None, 64)
    data.experience = _clip((data.experience or "unknown").strip(), 32) or "unknown"
    if data.skills:
        data.skills = sorted({s.strip() for s in data.skills if s and s.strip()})
    if data.currency:
        data.currency = _clip(data.currency.upper(), 8)
    if data.salary_from is not None:
        data.salary_from = int(data.salary_from)
        if data.salary_from <= 0:
            data.salary_from = None
    if data.salary_to is not None:
        data.salary_to = int(data.salary_to)
        if data.salary_to <= 0:
            data.salary_to = None
    salary_text = str((data.raw_data or {}).get("salary") or "")
    hint_text = " ".join(
        part
        for part in (
            data.salary_period,
            data.title,
            data.description,
            salary_text,
        )
        if part
    )
    hours = detect_hours_per_day(hint_text)
    period = detect_salary_period(
        hint_text,
        data.salary_from or data.salary_to,
        data.currency,
        explicit=data.salary_period,
        salary_text=salary_text,
    )
    data.salary_from = to_monthly_amount(data.salary_from, period, hours)
    data.salary_to = to_monthly_amount(data.salary_to, period, hours)
    data.salary_period = "monthly"
    if (
        data.salary_from is not None
        and data.salary_to is not None
        and data.salary_from > data.salary_to
    ):
        data.salary_from, data.salary_to = data.salary_to, data.salary_from
    return data


def parse_iso_datetime(value: str | int | float | None) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        try:
            ts = int(value)
            if ts > 10_000_000_000:
                ts //= 1000
            return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)
        except (OSError, ValueError, OverflowError):
            return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


EXPERIENCE_ALIASES = {
    "intern": ExperienceLevel.NO_EXPERIENCE,
    "entry-level": ExperienceLevel.NO_EXPERIENCE,
    "entry": ExperienceLevel.NO_EXPERIENCE,
    "junior": ExperienceLevel.BETWEEN_1_AND_3,
    "middle": ExperienceLevel.BETWEEN_1_AND_3,
    "mid": ExperienceLevel.BETWEEN_1_AND_3,
    "mid-level": ExperienceLevel.BETWEEN_1_AND_3,
    "midweight": ExperienceLevel.BETWEEN_1_AND_3,
    "regular": ExperienceLevel.BETWEEN_1_AND_3,
    "senior": ExperienceLevel.BETWEEN_3_AND_6,
    "lead": ExperienceLevel.MORE_THAN_6,
    "manager": ExperienceLevel.MORE_THAN_6,
    "director": ExperienceLevel.MORE_THAN_6,
    "principal": ExperienceLevel.MORE_THAN_6,
    "executive": ExperienceLevel.MORE_THAN_6,
}


def map_experience(value: str | list | None) -> str:
    if value is None:
        return ExperienceLevel.UNKNOWN
    if isinstance(value, list):
        value = value[0] if value else None
    if not value:
        return ExperienceLevel.UNKNOWN
    key = str(value).lower().strip()
    if key in EXPERIENCE_ALIASES:
        return EXPERIENCE_ALIASES[key]
    # "Senior Python" / "Mid-level" compounds
    for alias, level in EXPERIENCE_ALIASES.items():
        if alias in key:
            return level
    return ExperienceLevel.UNKNOWN


def map_work_format(value: str | None, *, remote_flag: bool | None = None) -> str:
    raw = (value or "").lower().strip()
    if remote_flag is True or raw in {"remote", "удалёнка", "удаленно", "удалённо"}:
        return WorkFormat.REMOTE
    if raw in {"hybrid", "гибрид"}:
        return WorkFormat.HYBRID
    if raw in {"office", "onsite", "on-site", "офис"}:
        return WorkFormat.OFFICE
    if remote_flag is False and raw:
        return WorkFormat.OFFICE
    return WorkFormat.UNKNOWN
