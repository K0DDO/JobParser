"""HeadHunter vacancy listing via public search RSS (no applicant API / no auto-apply).

Official applicant API was shut down; anonymous GET /vacancies returns 403.
Search RSS still returns public vacancy cards: https://hh.ru/search/vacancy/rss
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any

import httpx

from app.core.config import settings
from app.core.enums import ExperienceLevel, SourceName, WorkFormat
from app.parsers.base import ParserConfig, VacancySource
from app.schemas import VacancyData
from app.services.normalize import map_work_format, parse_iso_datetime

HH_RSS = "https://hh.ru/search/vacancy/rss"
VACANCY_ID_RE = re.compile(r"/vacancy/(\d+)")
COMPANY_RE = re.compile(r"Вакансия компании:\s*(.+?)(?:</p>|$)", re.I | re.S)
CITY_RE = re.compile(r"Регион:\s*(.+?)(?:</p>|$)", re.I | re.S)
SALARY_RE = re.compile(
    r"месячного дохода:\s*(.+?)(?:</p>|$)",
    re.I | re.S,
)
# HH search_period accepts only these day buckets.
HH_SEARCH_PERIODS = (1, 3, 7, 30)


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


class HHSource(VacancySource):
    name = SourceName.HH
    display_name = "HH"
    auto_apply_supported = False

    def __init__(self) -> None:
        self.user_agent = settings.hh_user_agent

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        }

    async def fetch_vacancies(self, config: ParserConfig) -> list[VacancyData]:
        from datetime import timedelta

        from app.core.timeutil import utc_now_naive

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

        async with httpx.AsyncClient(timeout=45.0, headers=self._headers(), follow_redirects=True) as client:
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
        return {**super().health(), "status": "ready", "mode": "rss", "auto_apply_supported": False}
