import hashlib
import re
from datetime import datetime
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


def normalize_vacancy(data: VacancyData) -> VacancyData:
    """Apply shared normalization rules to a vacancy payload."""
    data.title = (data.title or "").strip() or "Untitled"
    data.company = (data.company or "").strip() or None
    data.city = (data.city or "").strip() or None
    data.url = data.url.strip()
    if data.skills:
        data.skills = sorted({s.strip() for s in data.skills if s and s.strip()})
    if data.currency:
        data.currency = data.currency.upper()
    if data.salary_from is not None and data.salary_from < 0:
        data.salary_from = None
    if data.salary_to is not None and data.salary_to < 0:
        data.salary_to = None
    if (
        data.salary_from is not None
        and data.salary_to is not None
        and data.salary_from > data.salary_to
    ):
        data.salary_from, data.salary_to = data.salary_to, data.salary_from
    return data


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


EXPERIENCE_ALIASES = {
    "intern": ExperienceLevel.NO_EXPERIENCE,
    "junior": ExperienceLevel.BETWEEN_1_AND_3,
    "middle": ExperienceLevel.BETWEEN_1_AND_3,
    "mid": ExperienceLevel.BETWEEN_1_AND_3,
    "regular": ExperienceLevel.BETWEEN_1_AND_3,
    "senior": ExperienceLevel.BETWEEN_3_AND_6,
    "lead": ExperienceLevel.MORE_THAN_6,
    "director": ExperienceLevel.MORE_THAN_6,
    "principal": ExperienceLevel.MORE_THAN_6,
}


def map_experience(value: str | None) -> str:
    if not value:
        return ExperienceLevel.UNKNOWN
    return EXPERIENCE_ALIASES.get(value.lower().strip(), ExperienceLevel.UNKNOWN)


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
