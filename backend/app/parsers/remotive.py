"""Remotive public API — https://remotive.com/api/remote-jobs"""

from __future__ import annotations

import re
from typing import Any

import httpx

from app.core.enums import SourceName, WorkFormat
from app.parsers.base import ParserConfig, VacancySource
from app.parsers.http import DEFAULT_HEADERS
from app.schemas import VacancyData
from app.services.normalize import detect_salary_period, map_experience, map_work_format, parse_iso_datetime

REMOTIVE_API = "https://remotive.com/api/remote-jobs"


def _parse_salary(raw: Any) -> tuple[int | None, int | None, str | None]:
    if raw is None:
        return None, None, None
    text = str(raw).strip()
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


def normalize_remotive_item(item: dict[str, Any]) -> VacancyData:
    loc = item.get("candidate_required_location") or "Remote"
    work_format = map_work_format(str(loc), remote_flag=True)
    if work_format == WorkFormat.UNKNOWN:
        work_format = WorkFormat.REMOTE
    salary_from, salary_to, currency = _parse_salary(item.get("salary"))
    tags = [str(t) for t in (item.get("tags") or []) if t]
    return VacancyData(
        source=SourceName.REMOTIVE,
        source_vacancy_id=str(item["id"]),
        url=str(item.get("url") or f"https://remotive.com/remote-jobs/{item['id']}"),
        title=str(item.get("title") or "Untitled"),
        company=item.get("company_name"),
        description=item.get("description"),
        salary_from=salary_from,
        salary_to=salary_to,
        currency=currency,
        salary_period=detect_salary_period(
            str(item.get("salary") or ""),
            salary_from,
            currency,
            salary_text=str(item.get("salary") or ""),
        ),
        city=str(loc),
        remote=True,
        work_format=work_format,
        employment_type=item.get("job_type"),
        experience=map_experience(None),
        published_at=parse_iso_datetime(item.get("publication_date")),
        skills=tags,
        raw_data=item,
        source_metadata={"category": item.get("category")},
    )


class RemotiveSource(VacancySource):
    name = SourceName.REMOTIVE
    display_name = "Remotive"
    auto_apply_supported = False

    async def fetch_vacancies(self, config: ParserConfig) -> list[VacancyData]:
        query = (config.query or "").strip()
        params: dict[str, Any] = {}
        if query:
            params["search"] = query
        async with httpx.AsyncClient(timeout=45.0, headers=DEFAULT_HEADERS, follow_redirects=True) as client:
            try:
                response = await client.get(REMOTIVE_API, params=params or None)
            except httpx.HTTPError as exc:
                raise RuntimeError(f"Remotive parser failed: network error — {exc}") from exc
            if response.status_code >= 400:
                raise RuntimeError(f"Remotive parser failed: HTTP {response.status_code}")
            payload = response.json()
        jobs = payload.get("jobs") or []
        limit = config.max_pages * config.per_page
        return [normalize_remotive_item(j) for j in jobs[:limit] if isinstance(j, dict) and j.get("id")]
