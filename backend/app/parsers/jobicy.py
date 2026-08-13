"""Jobicy public API — https://jobicy.com/api/v2/remote-jobs"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.enums import SourceName, WorkFormat
from app.parsers.base import ParserConfig, VacancySource
from app.parsers.http import DEFAULT_HEADERS
from app.schemas import VacancyData
from app.services.normalize import map_experience, map_work_format, parse_iso_datetime

JOBICY_API = "https://jobicy.com/api/v2/remote-jobs"


def normalize_jobicy_item(item: dict[str, Any]) -> VacancyData:
    geo = item.get("jobGeo") or "Remote"
    work_format = map_work_format(str(geo), remote_flag=True)
    if work_format == WorkFormat.UNKNOWN:
        work_format = WorkFormat.REMOTE
    industry = item.get("jobIndustry")
    if isinstance(industry, list):
        skills = [str(x) for x in industry if x]
    elif industry:
        skills = [str(industry)]
    else:
        skills = []
    job_type = item.get("jobType")
    if isinstance(job_type, list):
        job_type = job_type[0] if job_type else None
    return VacancyData(
        source=SourceName.JOBICY,
        source_vacancy_id=str(item.get("id") or item.get("jobSlug")),
        url=str(item.get("url") or f"https://jobicy.com/job/{item.get('jobSlug')}"),
        title=str(item.get("jobTitle") or "Untitled"),
        company=item.get("companyName"),
        description=item.get("jobExcerpt") or item.get("jobDescription"),
        city=str(geo) if not isinstance(geo, list) else ", ".join(str(x) for x in geo[:3]),
        remote=True,
        work_format=work_format,
        employment_type=str(job_type) if job_type else None,
        experience=map_experience(item.get("jobLevel")),
        published_at=parse_iso_datetime(item.get("pubDate")),
        skills=skills,
        raw_data=item,
    )


class JobicySource(VacancySource):
    name = SourceName.JOBICY
    display_name = "Jobicy"
    auto_apply_supported = False

    async def fetch_vacancies(self, config: ParserConfig) -> list[VacancyData]:
        query = (config.query or "").strip()
        count = min(config.max_pages * config.per_page, 100)
        params: dict[str, Any] = {"count": count}
        if query:
            params["tag"] = query.split()[0]
        async with httpx.AsyncClient(timeout=45.0, headers=DEFAULT_HEADERS, follow_redirects=True) as client:
            try:
                response = await client.get(JOBICY_API, params=params)
            except httpx.HTTPError as exc:
                raise RuntimeError(f"Jobicy parser failed: network error — {exc}") from exc
            if response.status_code >= 400:
                raise RuntimeError(f"Jobicy parser failed: HTTP {response.status_code}")
            payload = response.json()
        jobs = payload.get("jobs") or []
        results = []
        for job in jobs:
            if not isinstance(job, dict) or not (job.get("id") or job.get("jobSlug")):
                continue
            try:
                results.append(normalize_jobicy_item(job))
            except Exception:
                continue
        if query:
            q = query.lower()
            results = [
                r
                for r in results
                if q in f"{r.title} {r.company or ''} {' '.join(r.skills)}".lower()
            ]
        return results
