"""HeadHunter official API parser — https://api.hh.ru/openapi/redoc"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx

from app.core.config import settings
from app.core.enums import ExperienceLevel, SourceName, WorkFormat
from app.parsers.base import ParserConfig, VacancySource
from app.schemas import VacancyData
from app.services.hh_auth import hh_headers

logger = logging.getLogger(__name__)

HH_API = "https://api.hh.ru"

EXPERIENCE_MAP = {
    "noExperience": ExperienceLevel.NO_EXPERIENCE,
    "between1And3": ExperienceLevel.BETWEEN_1_AND_3,
    "between3And6": ExperienceLevel.BETWEEN_3_AND_6,
    "moreThan6": ExperienceLevel.MORE_THAN_6,
}

SCHEDULE_TO_FORMAT = {
    "remote": WorkFormat.REMOTE,
    "flexible": WorkFormat.HYBRID,
    "fullDay": WorkFormat.OFFICE,
    "shift": WorkFormat.OFFICE,
    "flyInFlyOut": WorkFormat.OFFICE,
}


class HHSource(VacancySource):
    name = SourceName.HH
    display_name = "HH"
    auto_apply_supported = True  # via official API when token is present

    def __init__(self) -> None:
        self.user_agent = settings.hh_user_agent
        self.access_token = settings.hh_access_token

    def _token(self, config: ParserConfig | None = None) -> str:
        from_config = (config.sources_settings if config else {}).get("access_token") or ""
        return from_config or self.access_token

    def _headers(self, config: ParserConfig | None = None) -> dict[str, str]:
        return hh_headers(self._token(config) or None)

    async def fetch_vacancies(self, config: ParserConfig) -> list[VacancyData]:
        results: list[VacancyData] = []
        params_base: dict[str, Any] = {
            "per_page": min(config.per_page, 100),
            "order_by": "publication_time",
        }
        if config.query:
            params_base["text"] = config.query
        else:
            # Sensible default for local job search without a profile query
            params_base["text"] = "Python OR Backend OR FastAPI OR Django"

        async with httpx.AsyncClient(timeout=30.0, headers=self._headers(config)) as client:
            for page in range(config.max_pages):
                params = {**params_base, "page": page}
                try:
                    response = await client.get(f"{HH_API}/vacancies", params=params)
                except httpx.HTTPError as exc:
                    logger.error("HH fetch failed on page %s: %s", page, exc)
                    raise RuntimeError(f"HH parser failed: network error — {exc}") from exc

                if response.status_code >= 400:
                    detail = self._friendly_error(response)
                    logger.error("HH fetch failed on page %s: %s", page, detail)
                    raise RuntimeError(detail)

                response.raise_for_status()

                payload = response.json()
                items = payload.get("items") or []
                if not items:
                    break

                for item in items:
                    results.append(self._normalize(item))

                pages = payload.get("pages", 1)
                if page + 1 >= pages:
                    break

        return results

    def _normalize(self, item: dict[str, Any]) -> VacancyData:
        salary = item.get("salary") or {}
        area = item.get("area") or {}
        employer = item.get("employer") or {}
        experience = item.get("experience") or {}
        schedule = item.get("schedule") or {}
        employment = item.get("employment") or {}
        snippet = item.get("snippet") or {}

        schedule_id = schedule.get("id")
        work_format = SCHEDULE_TO_FORMAT.get(schedule_id, WorkFormat.UNKNOWN)
        remote = schedule_id == "remote"

        # HH also exposes work_format in newer API responses
        for wf in item.get("work_format") or []:
            if isinstance(wf, dict) and wf.get("id") == "REMOTE":
                remote = True
                work_format = WorkFormat.REMOTE

        published_raw = item.get("published_at") or item.get("created_at")
        published_at = None
        if published_raw:
            try:
                published_at = datetime.fromisoformat(published_raw.replace("Z", "+00:00")).replace(
                    tzinfo=None
                )
            except ValueError:
                published_at = None

        description_parts = [
            snippet.get("requirement") or "",
            snippet.get("responsibility") or "",
        ]
        description = "\n".join(p for p in description_parts if p).strip() or None

        skills = [s.get("name") for s in (item.get("key_skills") or []) if s.get("name")]

        return VacancyData(
            source=self.name,
            source_vacancy_id=str(item["id"]),
            url=item.get("alternate_url") or f"https://hh.ru/vacancy/{item['id']}",
            title=item.get("name") or "Untitled",
            company=employer.get("name"),
            description=description,
            salary_from=salary.get("from"),
            salary_to=salary.get("to"),
            currency=salary.get("currency"),
            salary_period="monthly",
            city=area.get("name"),
            remote=remote,
            work_format=work_format,
            employment_type=employment.get("id"),
            experience=EXPERIENCE_MAP.get(experience.get("id"), ExperienceLevel.UNKNOWN),
            published_at=published_at,
            skills=skills,
            raw_data=item,
            source_metadata={"schedule": schedule_id, "premium": item.get("premium")},
        )

    async def apply_to_vacancy(
        self,
        vacancy: VacancyData,
        cover_letter: str | None = None,
    ) -> dict[str, Any]:
        if not self.access_token:
            raise RuntimeError(
                "HH auto-apply requires HH_ACCESS_TOKEN. "
                "Obtain it via HH OAuth (https://dev.hh.ru/) and set in .env"
            )

        payload: dict[str, Any] = {"vacancy_id": vacancy.source_vacancy_id}
        if cover_letter:
            payload["message"] = cover_letter

        async with httpx.AsyncClient(timeout=30.0, headers=self._headers()) as client:
            response = await client.post(f"{HH_API}/negotiations", data=payload)
            if response.status_code >= 400:
                detail = response.text[:500]
                raise RuntimeError(f"HH apply failed ({response.status_code}): {detail}")
            return {"status": "applied", "response": response.json() if response.content else {}}

    @staticmethod
    def _friendly_error(response: httpx.Response) -> str:
        body = (response.text or "")[:500]
        if response.status_code == 400 and "bad_user_agent" in body:
            return (
                "HH parser failed: Bad User-Agent. "
                "Set HH_USER_AGENT in .env to a unique value with contact email "
                "(do not use example.com)."
            )
        if response.status_code in {403, 429}:
            return (
                f"HH parser failed: HTTP {response.status_code}. "
                "Vacancy API is blocked for this network/IP or rate-limited. "
                "Try from another network, register an app at https://dev.hh.ru/, "
                "and set HH_ACCESS_TOKEN / HH_USER_AGENT."
            )
        return f"HH parser failed: HTTP {response.status_code}: {body}"

    def health(self) -> dict[str, Any]:
        return {
            **super().health(),
            "status": "ready",
            "auth": "token" if self.access_token else "anonymous",
        }
