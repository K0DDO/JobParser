"""Himalayas public jobs API — https://himalayas.app/jobs/api"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.enums import SourceName, WorkFormat
from app.parsers.base import ParserConfig, VacancySource
from app.parsers.http import DEFAULT_HEADERS
from app.schemas import VacancyData
from app.services.normalize import map_experience, map_work_format, parse_iso_datetime

HIMALAYAS_SEARCH = "https://himalayas.app/jobs/api/search"
HIMALAYAS_BROWSE = "https://himalayas.app/jobs/api"


def normalize_himalayas_item(item: dict[str, Any]) -> VacancyData:
    guid = str(item.get("guid") or item.get("id") or item.get("applicationLink") or "")
    title = str(item.get("title") or "Untitled")
    company = item.get("companyName")
    categories = [str(c) for c in (item.get("categories") or []) if c]
    work_format = map_work_format("remote", remote_flag=True)
    if work_format == WorkFormat.UNKNOWN:
        work_format = WorkFormat.REMOTE
    url = item.get("applicationLink") or item.get("url") or f"https://himalayas.app/companies/{item.get('companySlug')}/jobs"
    s_from = item.get("minSalary")
    s_to = item.get("maxSalary")
    period = str(item.get("salaryPeriod") or "annual").lower()
    pub = item.get("pubDate") or item.get("publishedAt")
    if isinstance(pub, (int, float)):
        from datetime import datetime, timezone

        published_at = datetime.fromtimestamp(int(pub), tz=timezone.utc).replace(tzinfo=None)
    else:
        published_at = parse_iso_datetime(str(pub) if pub else None)
    locs = item.get("locationRestrictions") or []
    city = locs[0] if locs else "Remote"
    if isinstance(city, dict):
        city = city.get("name") or city.get("country") or "Remote"
    return VacancyData(
        source=SourceName.HIMALAYAS,
        source_vacancy_id=guid[:120] or f"{company}-{title}",
        url=str(url),
        title=title,
        company=company,
        description=item.get("excerpt") or item.get("description"),
        salary_from=int(s_from) if isinstance(s_from, (int, float)) else None,
        salary_to=int(s_to) if isinstance(s_to, (int, float)) else None,
        currency=item.get("currency") or ("USD" if s_from or s_to else None),
        salary_period=period,
        city=city,
        remote=True,
        work_format=work_format,
        employment_type=item.get("employmentType"),
        experience=map_experience(item.get("seniority") or item.get("experience")),
        published_at=published_at,
        skills=categories[:20],
        raw_data=item,
        source_metadata={"companySlug": item.get("companySlug")},
    )


class HimalayasSource(VacancySource):
    name = SourceName.HIMALAYAS
    display_name = "Himalayas"
    auto_apply_supported = False

    async def fetch_vacancies(self, config: ParserConfig) -> list[VacancyData]:
        query = (config.query or "").strip()
        results: list[VacancyData] = []
        async with httpx.AsyncClient(timeout=45.0, headers=DEFAULT_HEADERS, follow_redirects=True) as client:
            for page in range(1, config.max_pages + 1):
                try:
                    if query:
                        response = await client.get(
                            HIMALAYAS_SEARCH,
                            params={"q": query, "page": page, "sort": "recent"},
                        )
                    else:
                        response = await client.get(
                            HIMALAYAS_BROWSE,
                            params={"limit": min(config.per_page, 20), "offset": (page - 1) * 20},
                        )
                except httpx.HTTPError as exc:
                    raise RuntimeError(f"Himalayas parser failed: network error — {exc}") from exc
                if response.status_code >= 400:
                    raise RuntimeError(f"Himalayas parser failed: HTTP {response.status_code}")
                payload = response.json()
                jobs = payload.get("jobs") or []
                if not jobs:
                    break
                results.extend(normalize_himalayas_item(j) for j in jobs if isinstance(j, dict))
                total = int(payload.get("totalCount") or 0)
                if len(results) >= total:
                    break
        return results
