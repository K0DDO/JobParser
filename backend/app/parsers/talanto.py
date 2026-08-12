"""Talanto public search adapter — https://talanto.work/api/jobs"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.enums import SourceName, WorkFormat
from app.parsers.base import ParserConfig, VacancySource
from app.parsers.http import DEFAULT_HEADERS
from app.schemas import VacancyData
from app.services.normalize import map_experience, map_work_format, parse_iso_datetime

TALANTO_API = "https://talanto.work/api/jobs"
TALANTO_SITE = "https://talanto.work"


def normalize_talanto_item(item: dict[str, Any]) -> VacancyData:
    remote_type = item.get("remote_type")
    work_format = map_work_format(remote_type)
    remote = work_format == WorkFormat.REMOTE
    location = item.get("location")
    city = None
    if location and remote_type != "remote":
        city = str(location).split(",")[0].strip()
    elif location:
        city = str(location).split(",")[0].strip()

    return VacancyData(
        source=SourceName.TALANTO,
        source_vacancy_id=str(item["id"]),
        url=f"{TALANTO_SITE}/jobs/{item['id']}",
        title=item.get("title") or "Untitled",
        company=item.get("company"),
        description=None,
        salary_from=item.get("salary_min"),
        salary_to=item.get("salary_max"),
        currency=item.get("salary_currency"),
        city=city,
        remote=remote,
        work_format=work_format,
        employment_type=item.get("employment_type"),
        experience=map_experience(item.get("level")),
        published_at=parse_iso_datetime(item.get("published_at")),
        skills=list(item.get("skills") or []),
        raw_data=item,
        source_metadata={"freshness_status": item.get("freshness_status")},
    )


class TalantoSource(VacancySource):
    name = SourceName.TALANTO
    display_name = "Talanto"
    auto_apply_supported = False

    async def fetch_vacancies(self, config: ParserConfig) -> list[VacancyData]:
        results: list[VacancyData] = []
        query = config.query or "Python Backend"
        limit = min(config.per_page, 50)
        async with httpx.AsyncClient(timeout=30.0, headers=DEFAULT_HEADERS, follow_redirects=True) as client:
            for page in range(config.max_pages):
                offset = page * limit
                try:
                    response = await client.get(
                        TALANTO_API,
                        params={"q": query, "limit": limit, "offset": offset},
                    )
                except httpx.HTTPError as exc:
                    raise RuntimeError(f"Talanto parser failed: network error — {exc}") from exc
                if response.status_code >= 400:
                    raise RuntimeError(
                        f"Talanto parser failed: HTTP {response.status_code}: {response.text[:300]}"
                    )
                payload = response.json()
                items = payload.get("items") or []
                if not items:
                    break
                results.extend(normalize_talanto_item(item) for item in items)
                total = int(payload.get("total") or 0)
                if offset + limit >= total:
                    break
        return results

    def health(self) -> dict:
        return {**super().health(), "status": "ready"}
