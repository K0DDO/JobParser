"""Company career boards via Greenhouse / Lever / Ashby public APIs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

import httpx

from app.core.enums import SourceName, WorkFormat
from app.parsers.base import ParserConfig, VacancySource
from app.parsers.http import DEFAULT_HEADERS
from app.schemas import VacancyData
from app.services.normalize import map_work_format, parse_iso_datetime

AtsKind = Literal["greenhouse", "lever", "ashby"]

# Curated boards from Job_Search_Resources + verified ATS slugs
CAREER_BOARDS: list[tuple[str, AtsKind, str]] = [
    # Greenhouse
    ("GitLab", "greenhouse", "gitlab"),
    ("JetBrains", "greenhouse", "jetbrains"),
    ("Canonical", "greenhouse", "canonical"),
    ("Wise", "greenhouse", "wise"),
    ("ClickHouse", "greenhouse", "clickhouse"),
    ("Doist", "greenhouse", "doist"),
    ("Grafana Labs", "greenhouse", "grafanalabs"),
    ("HashiCorp", "greenhouse", "hashicorp"),
    ("Cloudflare", "greenhouse", "cloudflare"),
    ("Stripe", "greenhouse", "stripe"),
    ("Notion", "greenhouse", "notion"),
    ("Figma", "greenhouse", "figma"),
    ("Datadog", "greenhouse", "datadog"),
    ("Elastic", "greenhouse", "elastic"),
    ("MongoDB", "greenhouse", "mongodb"),
    ("Twilio", "greenhouse", "twilio"),
    ("Airbnb", "greenhouse", "airbnb"),
    ("Dropbox", "greenhouse", "dropbox"),
    ("Reddit", "greenhouse", "reddit"),
    ("Discord", "greenhouse", "discord"),
    ("Shopify", "greenhouse", "shopify"),
    ("Duolingo", "greenhouse", "duolingo"),
    ("Asana", "greenhouse", "asana"),
    ("Rippling", "greenhouse", "rippling"),
    ("Brex", "greenhouse", "brex"),
    ("Affirm", "greenhouse", "affirm"),
    ("Plaid", "greenhouse", "plaid"),
    # Lever
    ("Contentsquare", "lever", "contentsquare"),
    # Ashby
    ("PostHog", "ashby", "posthog"),
    ("Miro", "ashby", "miro"),
    ("n8n", "ashby", "n8n"),
]


def _ms_to_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        n = int(value)
        if n > 10_000_000_000:
            n //= 1000
        return datetime.fromtimestamp(n, tz=timezone.utc).replace(tzinfo=None)
    except (TypeError, ValueError, OSError):
        return None


def normalize_greenhouse(company: str, item: dict[str, Any]) -> VacancyData:
    loc = (item.get("location") or {}).get("name") if isinstance(item.get("location"), dict) else item.get("location")
    remote = "remote" in str(loc or "").lower()
    return VacancyData(
        source=SourceName.GREENHOUSE,
        source_vacancy_id=f"gh-{company.lower()}-{item['id']}",
        url=str(item.get("absolute_url") or ""),
        title=str(item.get("title") or "Untitled"),
        company=item.get("company_name") or company,
        city=str(loc) if loc else None,
        remote=remote,
        work_format=WorkFormat.REMOTE if remote else map_work_format(str(loc or ""), remote_flag=remote),
        published_at=parse_iso_datetime(item.get("updated_at") or item.get("first_published")),
        skills=[],
        raw_data=item,
        source_metadata={"ats": "greenhouse", "board": company},
    )


def normalize_lever(company: str, item: dict[str, Any]) -> VacancyData:
    cats = item.get("categories") or {}
    loc = cats.get("location") if isinstance(cats, dict) else None
    workplace = str(item.get("workplaceType") or "").lower()
    remote = workplace == "remote" or "remote" in str(loc or "").lower()
    return VacancyData(
        source=SourceName.GREENHOUSE,
        source_vacancy_id=f"lever-{item['id']}",
        url=str(item.get("hostedUrl") or item.get("applyUrl") or ""),
        title=str(item.get("text") or "Untitled"),
        company=company,
        city=str(loc) if loc else None,
        remote=remote,
        work_format=WorkFormat.REMOTE if remote else map_work_format(workplace or str(loc or ""), remote_flag=remote),
        employment_type=cats.get("commitment") if isinstance(cats, dict) else None,
        published_at=_ms_to_dt(item.get("createdAt")),
        skills=[],
        raw_data=item,
        source_metadata={"ats": "lever", "board": company},
    )


def normalize_ashby(company: str, item: dict[str, Any]) -> VacancyData:
    loc = item.get("location")
    remote = bool(item.get("isRemote")) or str(item.get("workplaceType") or "").lower() == "remote"
    return VacancyData(
        source=SourceName.GREENHOUSE,
        source_vacancy_id=f"ashby-{item['id']}",
        url=str(item.get("jobUrl") or item.get("applyUrl") or ""),
        title=str(item.get("title") or "Untitled"),
        company=company,
        city=str(loc) if loc else None,
        remote=remote,
        work_format=WorkFormat.REMOTE if remote else map_work_format(str(item.get("workplaceType") or loc or ""), remote_flag=remote),
        published_at=parse_iso_datetime(item.get("publishedAt")),
        skills=[str(item["department"])] if item.get("department") else [],
        raw_data=item,
        source_metadata={"ats": "ashby", "board": company},
    )


class GreenhouseSource(VacancySource):
    """Company careers aggregator (Greenhouse + Lever + Ashby)."""

    name = SourceName.GREENHOUSE
    display_name = "Company Careers"
    auto_apply_supported = False

    async def fetch_vacancies(self, config: ParserConfig) -> list[VacancyData]:
        query = (config.query or "").strip().lower()
        tokens = [t for t in query.split() if t]
        results: list[VacancyData] = []
        async with httpx.AsyncClient(timeout=30.0, headers=DEFAULT_HEADERS, follow_redirects=True) as client:
            for company, ats, slug in CAREER_BOARDS:
                batch: list[VacancyData] = []
                try:
                    if ats == "greenhouse":
                        response = await client.get(
                            f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
                            params={"content": "false"},
                        )
                        if response.status_code >= 400:
                            continue
                        jobs = (response.json() or {}).get("jobs") or []
                        batch = []
                        for j in jobs:
                            if not isinstance(j, dict) or not j.get("id"):
                                continue
                            try:
                                batch.append(normalize_greenhouse(company, j))
                            except Exception:
                                continue
                    elif ats == "lever":
                        response = await client.get(
                            f"https://api.lever.co/v0/postings/{slug}",
                            params={"mode": "json"},
                        )
                        if response.status_code >= 400:
                            continue
                        raw = response.json()
                        jobs = raw if isinstance(raw, list) else []
                        batch = [normalize_lever(company, j) for j in jobs if isinstance(j, dict) and j.get("id")]
                    else:
                        response = await client.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
                        if response.status_code >= 400:
                            continue
                        jobs = (response.json() or {}).get("jobs") or []
                        batch = [normalize_ashby(company, j) for j in jobs if isinstance(j, dict) and j.get("id")]
                except httpx.HTTPError:
                    continue

                for data in batch:
                    if not data.url:
                        continue
                    if tokens:
                        blob = f"{data.title} {data.company or ''} {data.city or ''}".lower()
                        if not all(t in blob for t in tokens):
                            continue
                    results.append(data)
        return results
