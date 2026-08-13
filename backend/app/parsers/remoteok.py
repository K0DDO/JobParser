"""Remote OK public API — https://remoteok.com/api (attribution required)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.enums import SourceName, WorkFormat
from app.parsers.base import ParserConfig, VacancySource
from app.parsers.http import DEFAULT_HEADERS
from app.schemas import VacancyData
from app.services.normalize import map_experience, map_work_format

REMOTEOK_API = "https://remoteok.com/api"


def normalize_remoteok_item(item: dict[str, Any]) -> VacancyData | None:
    if "id" not in item or not item.get("position"):
        return None
    tags = [str(t) for t in (item.get("tags") or []) if t]
    location = item.get("location")
    remote = True
    work_format = map_work_format(str(location or "remote"), remote_flag=True)
    if work_format == WorkFormat.UNKNOWN:
        work_format = WorkFormat.REMOTE

    published = None
    epoch = item.get("epoch")
    if epoch is not None:
        try:
            published = datetime.fromtimestamp(int(epoch), tz=timezone.utc).replace(tzinfo=None)
        except (TypeError, ValueError, OSError):
            published = None
    if published is None and item.get("date"):
        try:
            published = datetime.fromisoformat(str(item["date"]).replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            published = None

    url = item.get("url") or item.get("apply_url") or f"https://remoteok.com/remote-jobs/{item.get('slug') or item['id']}"
    return VacancyData(
        source=SourceName.REMOTEOK,
        source_vacancy_id=str(item["id"]),
        url=str(url),
        title=str(item.get("position") or "Untitled"),
        company=item.get("company"),
        description=item.get("description"),
        salary_from=item.get("salary_min"),
        salary_to=item.get("salary_max"),
        currency="USD" if item.get("salary_min") or item.get("salary_max") else None,
        salary_period="yearly",
        city=str(location) if location else "Remote",
        remote=remote,
        work_format=work_format,
        experience=map_experience(None),
        published_at=published,
        skills=tags,
        raw_data=item,
    )


class RemoteOKSource(VacancySource):
    name = SourceName.REMOTEOK
    display_name = "Remote OK"
    auto_apply_supported = False

    async def fetch_vacancies(self, config: ParserConfig) -> list[VacancyData]:
        query = (config.query or "").strip().lower()
        headers = {**DEFAULT_HEADERS, "User-Agent": "JobParser/1.0 (local; +https://github.com/K0DDO/JobParser)"}
        async with httpx.AsyncClient(timeout=45.0, headers=headers, follow_redirects=True) as client:
            try:
                response = await client.get(REMOTEOK_API)
            except httpx.HTTPError as exc:
                raise RuntimeError(f"RemoteOK parser failed: network error — {exc}") from exc
            if response.status_code >= 400:
                raise RuntimeError(f"RemoteOK parser failed: HTTP {response.status_code}")
            payload = response.json()
        if not isinstance(payload, list):
            return []

        results: list[VacancyData] = []
        for item in payload:
            if not isinstance(item, dict) or "legal" in item:
                continue
            data = normalize_remoteok_item(item)
            if data is None:
                continue
            if query:
                blob = f"{data.title} {data.company or ''} {' '.join(data.skills)}".lower()
                if query not in blob:
                    continue
            results.append(data)
            if len(results) >= config.max_pages * config.per_page:
                break
        return results
