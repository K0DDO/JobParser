"""Working Nomads jobs API — https://www.workingnomads.com/jobs"""

from __future__ import annotations

import re
from typing import Any

import httpx

from app.core.enums import SourceName, WorkFormat
from app.parsers.base import ParserConfig, VacancySource
from app.parsers.http import DEFAULT_HEADERS
from app.schemas import VacancyData
from app.services.normalize import (
    detect_salary_period,
    map_experience,
    map_work_format,
    parse_iso_datetime,
)

WN_SEARCH = "https://www.workingnomads.com/jobsapi/_search"
WN_SITE = "https://www.workingnomads.com"
POSITION_TYPES = {"ft": "Full-time", "pt": "Part-time", "fr": "Contract"}
_SOURCE_FIELDS = [
    "id",
    "slug",
    "title",
    "company",
    "category_name",
    "description",
    "position_type",
    "experience_level",
    "tags",
    "locations",
    "location_base",
    "pub_date",
    "apply_url",
    "annual_salary_usd",
    "salary_range",
    "salary_range_short",
]


def _strip_html(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"<[^>]+>", " ", value)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _parse_salary_text(raw: Any) -> tuple[int | None, int | None, str | None]:
    text = str(raw or "").strip()
    if not text:
        return None, None, None
    currency = None
    for cur in ("USD", "EUR", "GBP", "$", "€", "£"):
        if cur in text.upper() or cur in text:
            currency = {"$": "USD", "€": "EUR", "£": "GBP"}.get(cur, cur)
            break
    nums: list[int] = []
    for num, suffix in re.findall(r"(\d+(?:\.\d+)?)\s*([kKmM]?)", text.replace(",", "")):
        value = float(num)
        if suffix.lower() == "k":
            value *= 1000
        elif suffix.lower() == "m":
            value *= 1_000_000
        nums.append(int(value))
    if not nums:
        return None, None, currency
    if len(nums) == 1:
        return nums[0], None, currency or "USD"
    return nums[0], nums[1], currency or "USD"


def _salary(item: dict[str, Any]) -> tuple[int | None, int | None, str | None, str | None]:
    text = str(item.get("salary_range") or item.get("salary_range_short") or "").strip()
    if text:
        salary_from, salary_to, currency = _parse_salary_text(text)
        period = detect_salary_period(text, salary_from or salary_to, currency or "USD", salary_text=text)
        return salary_from, salary_to, currency or "USD", period
    annual = item.get("annual_salary_usd")
    if isinstance(annual, (int, float)) and annual > 0:
        return int(round(annual)), None, "USD", "yearly"
    return None, None, None, None


def normalize_workingnomads_item(item: dict[str, Any]) -> VacancyData | None:
    vid = item.get("id")
    slug = item.get("slug")
    if not vid and not slug:
        return None
    url = f"{WN_SITE}/jobs/{slug}" if slug else f"{WN_SITE}/job/go/{vid}/"
    loc = item.get("location_base") or ""
    if not loc:
        locs = item.get("locations") or []
        if isinstance(locs, list) and locs:
            loc = ", ".join(str(x) for x in locs[:3] if x)
        elif isinstance(locs, str):
            loc = locs
    loc = loc or "Remote"
    tags = item.get("tags") or []
    if isinstance(tags, str):
        skills = [t.strip() for t in tags.split(",") if t.strip()]
    else:
        skills = [str(t) for t in tags if t]
    category = item.get("category_name")
    if category and str(category) not in skills:
        skills.append(str(category))
    salary_from, salary_to, currency, period = _salary(item)
    pos = POSITION_TYPES.get(str(item.get("position_type") or "").lower())
    work_format = map_work_format(str(loc), remote_flag=True)
    if work_format == WorkFormat.UNKNOWN:
        work_format = WorkFormat.REMOTE
    return VacancyData(
        source=SourceName.WORKINGNOMADS,
        source_vacancy_id=str(vid or slug),
        url=str(item.get("apply_url") or url),
        title=str(item.get("title") or "Untitled"),
        company=item.get("company") or item.get("company_name"),
        description=_strip_html(item.get("description")),
        salary_from=salary_from,
        salary_to=salary_to,
        currency=currency,
        salary_period=period,
        city=str(loc),
        remote=True,
        work_format=work_format,
        employment_type=pos,
        experience=map_experience(item.get("experience_level")),
        published_at=parse_iso_datetime(item.get("pub_date")),
        skills=skills[:20],
        raw_data=item,
        source_metadata={"listing_url": url, "category": category},
    )


def _search_body(query: str | None, *, size: int, offset: int) -> dict[str, Any]:
    body: dict[str, Any] = {
        "from": max(0, offset),
        "size": max(1, min(size, 100)),
        "_source": _SOURCE_FIELDS,
        "sort": [{"premium": {"order": "desc"}}, {"pub_date": {"order": "desc"}}],
    }
    if query:
        tokens = [t.strip() for t in re.split(r"\s+OR\s+|\s+", query, flags=re.I) if t.strip()]
        tokens = list(dict.fromkeys(tokens))[:8]
        if tokens:
            qs = " OR ".join(tokens)
            body["query"] = {
                "bool": {
                    "must": [
                        {
                            "query_string": {
                                "query": qs,
                                "fields": ["title^2", "description", "company", "tags", "category_name"],
                            }
                        }
                    ]
                }
            }
    return body


class WorkingNomadsSource(VacancySource):
    name = SourceName.WORKINGNOMADS
    display_name = "Working Nomads"
    auto_apply_supported = False

    async def fetch_vacancies(self, config: ParserConfig) -> list[VacancyData]:
        query = (config.query or "").strip() or None
        limit = max(1, config.max_pages * config.per_page)
        page_size = min(100, max(config.per_page, 50))
        headers = {
            **DEFAULT_HEADERS,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Referer": f"{WN_SITE}/jobs",
        }
        results: list[VacancyData] = []
        seen: set[str] = set()
        async with httpx.AsyncClient(timeout=45.0, headers=headers, follow_redirects=True) as client:
            offset = 0
            while len(results) < limit:
                try:
                    response = await client.post(WN_SEARCH, json=_search_body(query, size=page_size, offset=offset))
                except httpx.HTTPError as exc:
                    raise RuntimeError(f"Working Nomads parser failed: network error — {exc}") from exc
                if response.status_code >= 400:
                    raise RuntimeError(f"Working Nomads parser failed: HTTP {response.status_code}")
                payload = response.json()
                hits = ((payload.get("hits") or {}).get("hits") or []) if isinstance(payload, dict) else []
                if not hits:
                    break
                for hit in hits:
                    item = hit.get("_source") if isinstance(hit, dict) else None
                    if not isinstance(item, dict):
                        continue
                    try:
                        data = normalize_workingnomads_item(item)
                    except Exception:
                        continue
                    if data is None or data.source_vacancy_id in seen:
                        continue
                    seen.add(data.source_vacancy_id)
                    results.append(data)
                    if len(results) >= limit:
                        break
                if len(hits) < page_size:
                    break
                offset += page_size
        if query:
            tokens = [t.lower() for t in re.split(r"\s+OR\s+|\s+", query, flags=re.I) if t.strip()]
            if tokens:
                results = [
                    r
                    for r in results
                    if any(
                        t in f"{r.title} {r.company or ''} {' '.join(r.skills)} {r.description or ''}".lower()
                        for t in tokens
                    )
                ]
        return results
