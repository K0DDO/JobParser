"""Arbeitnow public job board API — https://www.arbeitnow.com/api/job-board-api"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.enums import SourceName, WorkFormat
from app.parsers.base import ParserConfig, VacancySource
from app.parsers.http import DEFAULT_HEADERS
from app.schemas import VacancyData
from app.services.normalize import map_experience, map_work_format, parse_iso_datetime

ARBEITNOW_API = "https://www.arbeitnow.com/api/job-board-api"


def normalize_arbeitnow_item(item: dict[str, Any]) -> VacancyData:
    remote = bool(item.get("remote"))
    loc = item.get("location") or ("Remote" if remote else None)
    work_format = map_work_format(str(loc or ""), remote_flag=remote)
    if remote and work_format == WorkFormat.UNKNOWN:
        work_format = WorkFormat.REMOTE
    tags = [str(t) for t in (item.get("tags") or []) if t]
    types = item.get("job_types") or []
    employment = types[0] if types else None
    slug = item.get("slug") or item.get("url")
    return VacancyData(
        source=SourceName.ARBEITNOW,
        source_vacancy_id=str(slug),
        url=str(item.get("url") or f"https://www.arbeitnow.com/view/{slug}"),
        title=str(item.get("title") or "Untitled"),
        company=item.get("company_name"),
        description=item.get("description"),
        city=str(loc) if loc else None,
        remote=remote,
        work_format=work_format,
        employment_type=str(employment) if employment else None,
        experience=map_experience(None),
        published_at=parse_iso_datetime(item.get("created_at")),
        skills=tags,
        raw_data=item,
    )


class ArbeitnowSource(VacancySource):
    name = SourceName.ARBEITNOW
    display_name = "Arbeitnow"
    auto_apply_supported = False

    async def fetch_vacancies(self, config: ParserConfig) -> list[VacancyData]:
        query = (config.query or "").strip().lower()
        results: list[VacancyData] = []
        async with httpx.AsyncClient(timeout=45.0, headers=DEFAULT_HEADERS, follow_redirects=True) as client:
            for page in range(1, config.max_pages + 1):
                try:
                    response = await client.get(ARBEITNOW_API, params={"page": page})
                except httpx.HTTPError as exc:
                    raise RuntimeError(f"Arbeitnow parser failed: network error — {exc}") from exc
                if response.status_code >= 400:
                    raise RuntimeError(f"Arbeitnow parser failed: HTTP {response.status_code}")
                payload = response.json()
                items = payload.get("data") or []
                if not items:
                    break
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    try:
                        data = normalize_arbeitnow_item(item)
                    except Exception:
                        continue
                    if query:
                        blob = f"{data.title} {data.company or ''} {' '.join(data.skills)}".lower()
                        if query not in blob:
                            continue
                    results.append(data)
                links = payload.get("links") or {}
                if not links.get("next"):
                    break
        return results
