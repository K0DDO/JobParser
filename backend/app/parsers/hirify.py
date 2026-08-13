"""Hirify public search adapter — https://api.hirify.me/api/vacancies"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.enums import SourceName, WorkFormat
from app.parsers.base import ParserConfig, VacancySource
from app.parsers.http import DEFAULT_HEADERS
from app.schemas import VacancyData
from app.services.normalize import map_experience, map_work_format, parse_iso_datetime

HIRIFY_API = "https://api.hirify.me/api/vacancies"
HIRIFY_SITE = "https://hirify.me"


def normalize_hirify_item(item: dict[str, Any]) -> VacancyData:
    company = item.get("company_title")
    if company in {None, "", "%hirify_global%"}:
        company = None

    formats = item.get("work_format") or []
    format_raw = formats[0] if formats else item.get("remote_type")
    remote = "remote" in [str(x).lower() for x in formats] or str(item.get("remote_type") or "").lower() in {
        "remote",
        "world",
    }
    work_format = map_work_format(str(format_raw or ""), remote_flag=remote)
    if work_format == WorkFormat.UNKNOWN and remote:
        work_format = WorkFormat.REMOTE

    grades = item.get("grades") or []
    grade_name = grades[0].get("name") if grades else None
    regions = item.get("regions") or []
    city = None
    if regions:
        city = regions[0].get("name") or regions[0].get("name_en")

    salary = item.get("salary") or {}
    salary_from = salary.get("from") if isinstance(salary, dict) else None
    salary_to = salary.get("to") if isinstance(salary, dict) else None
    currency = salary.get("currency") if isinstance(salary, dict) else None

    tags = item.get("tags") or []
    skills = [t.get("name") for t in tags if isinstance(t, dict) and t.get("name")]
    slug = item.get("slug") or str(item.get("id"))

    return VacancyData(
        source=SourceName.HIRIFY,
        source_vacancy_id=str(item["id"]),
        url=f"{HIRIFY_SITE}/jobs/{slug}",
        title=item.get("title") or item.get("original_title") or "Untitled",
        company=company,
        description=item.get("tldr"),
        salary_from=salary_from,
        salary_to=salary_to,
        currency=currency,
        salary_period="monthly",
        city=city,
        remote=work_format == WorkFormat.REMOTE,
        work_format=work_format,
        employment_type=item.get("work_type"),
        experience=map_experience(grade_name),
        published_at=parse_iso_datetime(item.get("created_at") or item.get("updated_at")),
        skills=skills,
        raw_data=item,
        source_metadata={"source": item.get("source"), "premium": item.get("premium")},
    )


class HirifySource(VacancySource):
    name = SourceName.HIRIFY
    display_name = "Hirify"
    auto_apply_supported = False

    async def fetch_vacancies(self, config: ParserConfig) -> list[VacancyData]:
        results: list[VacancyData] = []
        query = config.query or "Python Backend"
        async with httpx.AsyncClient(timeout=30.0, headers=DEFAULT_HEADERS, follow_redirects=True) as client:
            for page in range(1, config.max_pages + 1):
                try:
                    response = await client.get(HIRIFY_API, params={"search": query, "page": page})
                except httpx.HTTPError as exc:
                    raise RuntimeError(f"Hirify parser failed: network error — {exc}") from exc
                if response.status_code >= 400:
                    raise RuntimeError(
                        f"Hirify parser failed: HTTP {response.status_code}: {response.text[:300]}"
                    )
                payload = response.json()
                items = payload.get("data") or []
                if not items:
                    break
                results.extend(normalize_hirify_item(item) for item in items)
                last_page = int(payload.get("last_page") or 1)
                if page >= last_page:
                    break
        return results

    def health(self) -> dict:
        return {**super().health(), "status": "ready"}
