"""HeadHunter vacancy listing via official search API, with public RSS fallback.

Applicant negotiations API is not used (no auto-apply). Listing uses GET /vacancies
with the registered application User-Agent and OAuth / client_credentials token.
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any

import httpx

from app.core.config import settings
from app.core.enums import ExperienceLevel, SourceName, WorkFormat
from app.core.timeutil import utc_now_naive
from app.parsers.base import ParserConfig, VacancySource
from app.schemas import VacancyData
from app.services.hh_auth import HH_API, exchange_client_credentials, hh_headers
from app.services.normalize import map_experience, map_work_format, parse_iso_datetime

logger = logging.getLogger(__name__)

HH_RSS = "https://hh.ru/search/vacancy/rss"
VACANCY_ID_RE = re.compile(r"/vacancy/(\d+)")
COMPANY_RE = re.compile(r"Вакансия компании:\s*(.+?)(?:</p>|$)", re.I | re.S)
CITY_RE = re.compile(r"Регион:\s*(.+?)(?:</p>|$)", re.I | re.S)
SALARY_RE = re.compile(
    r"месячного дохода:\s*(.+?)(?:</p>|$)",
    re.I | re.S,
)
# HH search_period / period accepts only these day buckets on RSS; API period max is 30.
HH_SEARCH_PERIODS = (1, 3, 7, 30)

_HH_EXPERIENCE = {
    "noexperience": ExperienceLevel.NO_EXPERIENCE,
    "between1and3": ExperienceLevel.BETWEEN_1_AND_3,
    "between3and6": ExperienceLevel.BETWEEN_3_AND_6,
    "morethan6": ExperienceLevel.MORE_THAN_6,
}
_HH_SCHEDULE = {
    "remote": WorkFormat.REMOTE,
    "flexible": WorkFormat.HYBRID,
    "fullday": WorkFormat.OFFICE,
    "shift": WorkFormat.OFFICE,
    "flyinflyout": WorkFormat.OFFICE,
}
_HH_WORK_FORMAT = {
    "remote": WorkFormat.REMOTE,
    "hybrid": WorkFormat.HYBRID,
    "on_site": WorkFormat.OFFICE,
    "field_work": WorkFormat.OFFICE,
}
_HH_PERIOD = {
    "hour": "hourly",
    "day": "daily",
    "month": "monthly",
    "year": "yearly",
}


def hh_search_period(lookback_days: int | None) -> int | None:
    """Map lookback days to nearest HH search_period bucket."""
    if lookback_days is None or lookback_days <= 0:
        return None
    for days in HH_SEARCH_PERIODS:
        if lookback_days <= days:
            return days
    return HH_SEARCH_PERIODS[-1]


def _xml_text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return (el.text or "").strip()


def _clean_html_fragment(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    text = text.replace("\xa0", " ").replace("\u202f", " ")
    return re.sub(r"\s+", " ", text).strip()


def _parse_money(raw: str | None) -> int | None:
    if not raw:
        return None
    digits = re.sub(r"[^\d]", "", raw)
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def _parse_salary_blob(blob: str) -> tuple[int | None, int | None, str | None]:
    text = _clean_html_fragment(blob)
    if not text or "не указан" in text.lower():
        return None, None, None
    currency = None
    if "₽" in text or "руб" in text.lower() or "rub" in text.lower():
        currency = "RUB"
    elif "$" in text or "usd" in text.lower():
        currency = "USD"
    elif "€" in text or "eur" in text.lower():
        currency = "EUR"

    low = high = None
    from_m = re.search(r"от\s*([\d\s\u00a0\u202f]+)", text, re.I)
    to_m = re.search(r"до\s*([\d\s\u00a0\u202f]+)", text, re.I)
    if from_m:
        low = _parse_money(from_m.group(1))
    if to_m:
        high = _parse_money(to_m.group(1))
    if low is None and high is None:
        nums = re.findall(r"[\d\s\u00a0\u202f]{2,}", text)
        parsed = [_parse_money(n) for n in nums]
        parsed = [n for n in parsed if n]
        if len(parsed) == 1:
            low = parsed[0]
        elif len(parsed) >= 2:
            low, high = parsed[0], parsed[1]
    return low, high, currency


def _hh_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    parsed = parse_iso_datetime(text)
    if parsed is not None:
        return parsed
    # HH sometimes sends +0300 without a colon.
    tweaked = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", text)
    return parse_iso_datetime(tweaked)


def _dict_id(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("id") or "").strip()
    return str(value or "").strip()


def _dict_name(value: Any) -> str | None:
    if isinstance(value, dict):
        name = str(value.get("name") or "").strip()
        return name or None
    text = str(value or "").strip()
    return text or None


def _hh_salary(item: dict[str, Any]) -> tuple[int | None, int | None, str | None, str | None]:
    blob = item.get("salary_range") if isinstance(item.get("salary_range"), dict) else None
    if blob is None and isinstance(item.get("salary"), dict):
        blob = item["salary"]
    if not blob:
        return None, None, None, None
    currency = str(blob.get("currency") or "").upper() or None
    if currency == "RUR":
        currency = "RUB"
    period = "monthly"
    mode = blob.get("mode")
    mode_id = _dict_id(mode).lower()
    if mode_id:
        period = _HH_PERIOD.get(mode_id, period)
    low = blob.get("from")
    high = blob.get("to")
    try:
        low_i = int(low) if low is not None else None
    except (TypeError, ValueError):
        low_i = None
    try:
        high_i = int(high) if high is not None else None
    except (TypeError, ValueError):
        high_i = None
    return low_i, high_i, currency, period


def _hh_work_format(item: dict[str, Any]) -> tuple[bool, str]:
    formats = item.get("work_format")
    if isinstance(formats, list):
        ids = {_dict_id(x).lower() for x in formats if x}
        if "remote" in ids:
            return True, WorkFormat.REMOTE
        if "hybrid" in ids:
            return False, WorkFormat.HYBRID
        for fid in ids:
            mapped = _HH_WORK_FORMAT.get(fid)
            if mapped:
                return mapped == WorkFormat.REMOTE, mapped
    schedule_id = _dict_id(item.get("schedule")).lower()
    if schedule_id in _HH_SCHEDULE:
        fmt = _HH_SCHEDULE[schedule_id]
        return fmt == WorkFormat.REMOTE, fmt
    area_name = _dict_name(item.get("area"))
    return False, map_work_format(area_name, remote_flag=False)


def normalize_hh_api_item(item: dict[str, Any]) -> VacancyData | None:
    vid = str(item.get("id") or "").strip()
    if not vid:
        url = str(item.get("alternate_url") or item.get("url") or "")
        match = VACANCY_ID_RE.search(url)
        if not match:
            return None
        vid = match.group(1)
    title = str(item.get("name") or "Untitled").strip() or "Untitled"
    employer = item.get("employer") if isinstance(item.get("employer"), dict) else {}
    company = _dict_name(employer)
    area_name = _dict_name(item.get("area"))
    salary_from, salary_to, currency, salary_period = _hh_salary(item)
    snippet = item.get("snippet") if isinstance(item.get("snippet"), dict) else {}
    parts = [snippet.get("requirement"), snippet.get("responsibility")]
    description = " ".join(str(p).strip() for p in parts if p)
    description = _clean_html_fragment(description) or None
    remote, work_format = _hh_work_format(item)
    exp_id = _dict_id(item.get("experience")).lower()
    experience = _HH_EXPERIENCE.get(exp_id) or map_experience(_dict_name(item.get("experience")))
    employment = _dict_name(item.get("employment")) or _dict_name(item.get("employment_form"))
    skills: list[str] = []
    for skill in item.get("key_skills") or []:
        name = _dict_name(skill) if not isinstance(skill, str) else skill.strip()
        if name:
            skills.append(name)
    url = str(item.get("alternate_url") or "").strip() or f"https://hh.ru/vacancy/{vid}"
    return VacancyData(
        source=SourceName.HH,
        source_vacancy_id=vid,
        url=url,
        title=title,
        company=company,
        description=description,
        salary_from=salary_from,
        salary_to=salary_to,
        currency=currency,
        salary_period=salary_period,
        city=area_name,
        remote=remote,
        work_format=work_format,
        employment_type=employment,
        experience=experience,
        published_at=_hh_datetime(item.get("published_at") or item.get("created_at")),
        skills=skills,
        raw_data=item,
        source_metadata={"via": "api"},
    )


def normalize_hh_rss_item(item: dict[str, Any]) -> VacancyData | None:
    link = str(item.get("link") or item.get("guid") or "")
    m = VACANCY_ID_RE.search(link)
    if not m:
        return None
    vid = m.group(1)
    desc_html = str(item.get("description") or "")
    company_m = COMPANY_RE.search(desc_html)
    city_m = CITY_RE.search(desc_html)
    salary_m = SALARY_RE.search(desc_html)
    company = _clean_html_fragment(company_m.group(1)) if company_m else None
    city = _clean_html_fragment(city_m.group(1)) if city_m else None
    salary_from = salary_to = currency = None
    if salary_m:
        salary_from, salary_to, currency = _parse_salary_blob(salary_m.group(1))

    title = str(item.get("title") or "Untitled").strip() or "Untitled"
    remote = False
    work_format = WorkFormat.UNKNOWN
    if city and "удал" in city.lower():
        remote = True
        work_format = WorkFormat.REMOTE
    elif city:
        work_format = map_work_format(city, remote_flag=False)

    published = parse_iso_datetime(item.get("pubDate"))
    if published is None and item.get("pubDate"):
        try:
            published = datetime.fromisoformat(str(item["pubDate"]).replace("Z", "+00:00")).replace(
                tzinfo=None
            )
        except ValueError:
            published = None

    return VacancyData(
        source=SourceName.HH,
        source_vacancy_id=vid,
        url=f"https://hh.ru/vacancy/{vid}",
        title=title,
        company=company,
        description=_clean_html_fragment(desc_html) or None,
        salary_from=salary_from,
        salary_to=salary_to,
        currency=currency,
        salary_period="monthly",
        city=city,
        remote=remote,
        work_format=work_format,
        experience=ExperienceLevel.UNKNOWN,
        published_at=published,
        skills=[],
        raw_data=item,
        source_metadata={"via": "rss"},
    )


def _resolve_parser_token(config: ParserConfig) -> str:
    stored = (config.sources_settings or {}).get("access_token") or ""
    return str(stored or settings.hh_access_token or "")


class HHSource(VacancySource):
    name = SourceName.HH
    display_name = "HH"
    auto_apply_supported = False

    def __init__(self) -> None:
        self.user_agent = settings.hh_user_agent
        self._last_mode = "api"

    async def fetch_vacancies(self, config: ParserConfig) -> list[VacancyData]:
        token = _resolve_parser_token(config)
        if not token and settings.hh_client_id and settings.hh_client_secret:
            try:
                payload = await exchange_client_credentials()
                token = str(payload.get("access_token") or "")
            except Exception as exc:  # noqa: BLE001
                logger.warning("HH client_credentials failed: %s", exc)

        try:
            items = await self._fetch_api(config, token or None)
            self._last_mode = "api"
            return items
        except RuntimeError as exc:
            if token:
                raise
            logger.warning("HH API listing failed without token, falling back to RSS: %s", exc)
            self._last_mode = "rss"
            return await self._fetch_rss(config)

    async def _fetch_api(self, config: ParserConfig, token: str | None) -> list[VacancyData]:
        query = (config.query or "").strip() or "Python Backend FastAPI Django"
        per_page = max(1, min(int(config.per_page or 50), 100))
        max_pages = max(1, int(config.max_pages or 5))
        period = hh_search_period(config.lookback_days)
        cutoff = None
        if config.lookback_days and config.lookback_days > 0:
            cutoff = utc_now_naive() - timedelta(days=config.lookback_days)

        results: list[VacancyData] = []
        seen: set[str] = set()
        headers = hh_headers(token)
        async with httpx.AsyncClient(timeout=45.0, headers=headers, follow_redirects=True) as client:
            for page in range(max_pages):
                params: dict[str, Any] = {
                    "text": query[:300],
                    "order_by": "publication_time",
                    "page": page,
                    "per_page": per_page,
                }
                if period is not None:
                    params["period"] = period
                try:
                    response = await client.get(f"{HH_API}/vacancies", params=params)
                except httpx.HTTPError as exc:
                    raise RuntimeError(f"HH API parser failed: network error — {exc}") from exc
                if response.status_code >= 400:
                    raise RuntimeError(
                        f"HH API parser failed: HTTP {response.status_code} {response.text[:300]}"
                    )
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise RuntimeError("HH API parser failed: invalid JSON") from exc
                items = payload.get("items") if isinstance(payload, dict) else None
                if not isinstance(items, list) or not items:
                    break
                new_on_page = 0
                page_too_old = False
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    try:
                        data = normalize_hh_api_item(item)
                    except Exception:  # noqa: BLE001
                        continue
                    if data is None or data.source_vacancy_id in seen:
                        continue
                    if cutoff is not None and data.published_at is not None and data.published_at < cutoff:
                        page_too_old = True
                        continue
                    seen.add(data.source_vacancy_id)
                    results.append(data)
                    new_on_page += 1
                    if len(results) >= max_pages * per_page:
                        return results
                pages_total = payload.get("pages")
                if isinstance(pages_total, int) and page + 1 >= pages_total:
                    break
                if new_on_page == 0 and page_too_old:
                    break
                if new_on_page == 0:
                    break
        return results

    async def _fetch_rss(self, config: ParserConfig) -> list[VacancyData]:
        query = (config.query or "").strip() or "Python Backend FastAPI Django"
        tokens = [t.strip() for t in re.split(r"\s+OR\s+|\s+", query, flags=re.I) if t.strip()]
        tokens = list(dict.fromkeys(tokens))[:6] or ["Python"]
        limit = max(1, config.max_pages * config.per_page)
        pages_per_term = max(1, min(config.max_pages, 8))
        search_period = hh_search_period(config.lookback_days)
        cutoff = None
        if config.lookback_days and config.lookback_days > 0:
            cutoff = utc_now_naive() - timedelta(days=config.lookback_days)
        results: list[VacancyData] = []
        seen: set[str] = set()
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        }

        async with httpx.AsyncClient(timeout=45.0, headers=headers, follow_redirects=True) as client:
            for token in tokens:
                for page in range(pages_per_term):
                    params: dict[str, Any] = {
                        "text": token[:120],
                        "order_by": "publication_time",
                        "page": page,
                    }
                    if search_period is not None:
                        params["search_period"] = search_period
                    try:
                        response = await client.get(HH_RSS, params=params)
                    except httpx.HTTPError as exc:
                        raise RuntimeError(f"HH RSS parser failed: network error — {exc}") from exc
                    if response.status_code >= 400:
                        raise RuntimeError(f"HH RSS parser failed: HTTP {response.status_code}")
                    try:
                        root = ET.fromstring(response.text)
                    except ET.ParseError as exc:
                        raise RuntimeError(f"HH RSS parser failed: invalid XML — {exc}") from exc
                    channel = root.find("channel")
                    if channel is None:
                        break
                    items = channel.findall("item")
                    if not items:
                        break
                    new_on_page = 0
                    page_too_old = False
                    for node in items:
                        item = {
                            "title": _xml_text(node.find("title")),
                            "link": _xml_text(node.find("link")),
                            "guid": _xml_text(node.find("guid")),
                            "description": _xml_text(node.find("description")),
                            "pubDate": _xml_text(node.find("pubDate")),
                        }
                        try:
                            data = normalize_hh_rss_item(item)
                        except Exception:  # noqa: BLE001
                            continue
                        if data is None or data.source_vacancy_id in seen:
                            continue
                        if cutoff is not None and data.published_at is not None and data.published_at < cutoff:
                            page_too_old = True
                            continue
                        seen.add(data.source_vacancy_id)
                        results.append(data)
                        new_on_page += 1
                        if len(results) >= limit:
                            return results
                    if new_on_page == 0 and page_too_old:
                        break
                    if new_on_page == 0:
                        break
        return results

    def health(self) -> dict[str, Any]:
        return {
            **super().health(),
            "status": "ready",
            "mode": self._last_mode,
            "auto_apply_supported": False,
        }
