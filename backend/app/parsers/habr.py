"""Habr Career public search adapter.

Uses the public frontend JSON API. Auto-apply is not supported.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

from app.core.enums import ExperienceLevel, SourceName, WorkFormat
from app.parsers.base import ParserConfig, VacancySource
from app.schemas import VacancyData

logger = logging.getLogger(__name__)

HABR_API = "https://career.habr.com/api/frontend/vacancies"
HABR_SITE = "https://career.habr.com"

QUALIFICATION_MAP = {
    "intern": ExperienceLevel.NO_EXPERIENCE,
    "junior": ExperienceLevel.BETWEEN_1_AND_3,
    "middle": ExperienceLevel.BETWEEN_1_AND_3,
    "senior": ExperienceLevel.BETWEEN_3_AND_6,
    "lead": ExperienceLevel.MORE_THAN_6,
}


class HabrSource(VacancySource):
    name = SourceName.HABR
    display_name = "Habr Career"
    auto_apply_supported = False

    async def fetch_vacancies(self, config: ParserConfig) -> list[VacancyData]:
        results: list[VacancyData] = []
        query = config.query or "Python Backend FastAPI"
        headers = {
            "User-Agent": "JobParserLocal/1.0 (personal; local-app)",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0, headers=headers, follow_redirects=True) as client:
            for page in range(1, config.max_pages + 1):
                params = {
                    "q": query,
                    "sort": "date",
                    "type": "all",
                    "page": page,
                }
                try:
                    response = await client.get(HABR_API, params=params)
                except httpx.HTTPError as exc:
                    raise RuntimeError(f"Habr parser failed: network error — {exc}") from exc

                if response.status_code >= 400:
                    raise RuntimeError(
                        f"Habr parser failed: HTTP {response.status_code}: {response.text[:300]}"
                    )

                payload = response.json()
                items = payload.get("list") or []
                if not items:
                    break

                for item in items:
                    results.append(self._normalize(item))

                meta = payload.get("meta") or {}
                total_pages = int(meta.get("totalPages") or 1)
                if page >= total_pages:
                    break

        return results

    def _normalize(self, item: dict[str, Any]) -> VacancyData:
        company = item.get("company") or {}
        salary = item.get("salary") or {}
        published = (item.get("publishedDate") or {}).get("date")
        published_at = None
        if published:
            try:
                published_at = datetime.fromisoformat(published.replace("Z", "+00:00")).replace(
                    tzinfo=None
                )
            except ValueError:
                published_at = None

        locations = item.get("locations") or []
        city = locations[0].get("title") if locations else None
        remote = bool(item.get("remoteWork"))
        if remote:
            work_format = WorkFormat.REMOTE
        elif city:
            work_format = WorkFormat.OFFICE
        else:
            work_format = WorkFormat.UNKNOWN

        qualification = (item.get("qualification") or "").lower()
        experience = QUALIFICATION_MAP.get(qualification, ExperienceLevel.UNKNOWN)

        skills = [s.get("title") for s in (item.get("skills") or []) if s.get("title")]
        href = item.get("href") or f"/vacancies/{item.get('id')}"
        url = href if str(href).startswith("http") else f"{HABR_SITE}{href}"

        currency = salary.get("currency")
        if currency:
            currency = str(currency).upper()
            if currency == "RUR":
                currency = "RUB"

        return VacancyData(
            source=self.name,
            source_vacancy_id=str(item["id"]),
            url=url,
            title=item.get("title") or "Untitled",
            company=company.get("title"),
            description=None,
            salary_from=salary.get("from"),
            salary_to=salary.get("to"),
            currency=currency,
            salary_period="monthly",
            city=city,
            remote=remote,
            work_format=work_format,
            employment_type=item.get("employment"),
            experience=experience,
            published_at=published_at,
            skills=skills,
            raw_data=item,
            source_metadata={"qualification": item.get("qualification")},
        )

    def health(self) -> dict:
        return {**super().health(), "status": "ready", "auto_apply_supported": False}
