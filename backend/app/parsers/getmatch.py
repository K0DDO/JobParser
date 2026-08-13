"""GetMatch public adapter.

Candidate listing is public: GET /api/offers (no login).
`/api/vacancies` is a recruiter endpoint and returns 401 — we do not use it.
Sitemap + JSON-LD remains a fallback if /api/offers is down.
Auto-apply is not supported.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import httpx

from app.core.enums import SourceName, WorkFormat
from app.parsers.base import ParserConfig, VacancySource
from app.parsers.http import DEFAULT_HEADERS
from app.schemas import VacancyData
from app.services.normalize import map_experience, map_work_format, parse_iso_datetime

GETMATCH_SITEMAP = "https://getmatch.ru/sitemap.xml"
GETMATCH_OFFERS = "https://getmatch.ru/api/offers"
GETMATCH_SITE = "https://getmatch.ru"
VACANCY_RE = re.compile(r"https://getmatch\.ru/vacancies/(\d+)-([^<]+)")
LD_RE = re.compile(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S)
OG_DESC_RE = re.compile(r'property="og:description" content="([^"]+)"')
OG_TITLE_RE = re.compile(r'property="og:title" content="([^"]+)"')
COMPANY_RE = re.compile(r"работ[ае]\s+в\s+компании\s+([^,.]+)", re.I)
SALARY_RE = re.compile(
    r"(\d[\d\s]{2,9})\s*[—\-–]\s*(\d[\d\s]{2,9})\s*([₽$€]|RUB|USD|EUR)?",
    re.I,
)


def _query_tokens(query: str | None) -> list[str]:
    if not query:
        return ["python", "backend"]
    parts = re.split(r"[,\s/|]+|(?:\bOR\b)|(?:\bAND\b)", query, flags=re.I)
    return [p.lower().strip() for p in parts if len(p.strip()) > 2]


def filter_sitemap_urls(xml_text: str, query: str | None, limit: int) -> list[str]:
    tokens = _query_tokens(query)
    scored: list[tuple[int, str]] = []
    fallback: list[tuple[int, str]] = []
    for match in VACANCY_RE.finditer(xml_text):
        url = match.group(0)
        slug = match.group(2).lower()
        vid = int(match.group(1))
        fallback.append((vid, url))
        if any(token in slug for token in tokens):
            scored.append((vid, url))
    pool = scored or fallback
    pool.sort(key=lambda item: item[0], reverse=True)
    seen: set[str] = set()
    urls: list[str] = []
    for _, url in pool:
        if url in seen:
            continue
        seen.add(url)
        urls.append(url)
        if len(urls) >= limit:
            break
    return urls


def _walk_jsonld(node: Any) -> dict[str, Any] | None:
    if isinstance(node, list):
        for item in node:
            found = _walk_jsonld(item)
            if found:
                return found
        return None
    if not isinstance(node, dict):
        return None
    types = node.get("@type")
    type_list = types if isinstance(types, list) else [types]
    if any(str(t).endswith("JobPosting") for t in type_list if t):
        return node
    if "@graph" in node:
        return _walk_jsonld(node["@graph"])
    return None


def _extract_jobposting(html: str) -> dict[str, Any] | None:
    for block in LD_RE.findall(html):
        try:
            payload = json.loads(block)
        except json.JSONDecodeError:
            continue
        found = _walk_jsonld(payload)
        if found:
            return found
    return None


def _int_money(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value).replace(" ", "").replace("\xa0", ""))
    except (TypeError, ValueError):
        return None


def _salary_from_text(text: str) -> tuple[int | None, int | None, str | None]:
    match = SALARY_RE.search(text.replace("\xa0", " "))
    if not match:
        return None, None, None
    low = _int_money(match.group(1))
    high = _int_money(match.group(2))
    raw_cur = (match.group(3) or "").strip()
    currency = {"₽": "RUB", "$": "USD", "€": "EUR"}.get(raw_cur, raw_cur.upper() or None)
    return low, high, currency


def normalize_getmatch_offer(item: dict[str, Any]) -> VacancyData:
    source_id = str(item["id"])
    href = item.get("url") or f"/vacancies/{source_id}"
    url = href if str(href).startswith("http") else f"{GETMATCH_SITE}{href}"

    company_raw = item.get("company") or {}
    company = company_raw.get("name") if isinstance(company_raw, dict) else None

    locations = item.get("location_items") or []
    city = None
    formats: list[str] = []
    for loc in locations:
        if not isinstance(loc, dict) or loc.get("exclude"):
            continue
        if city is None:
            city = loc.get("label") or loc.get("city")
        if loc.get("format"):
            formats.append(str(loc["format"]))
    remote = "remote" in [f.lower() for f in formats]
    work_format = map_work_format(formats[0] if formats else None, remote_flag=remote)

    skills: list[str] = []
    for skill in item.get("skills_objects") or []:
        if isinstance(skill, dict) and skill.get("name"):
            skills.append(str(skill["name"]))
        elif isinstance(skill, str) and skill.strip():
            skills.append(skill.strip())

    salary_from = item.get("salary_display_from")
    salary_to = item.get("salary_display_to")
    try:
        salary_from = int(salary_from) if salary_from is not None else None
        salary_to = int(salary_to) if salary_to is not None else None
    except (TypeError, ValueError):
        salary_from = salary_to = None

    return VacancyData(
        source=SourceName.GETMATCH,
        source_vacancy_id=source_id,
        url=url,
        title=item.get("position") or "Untitled",
        company=company,
        description=item.get("offer_description"),
        salary_from=salary_from,
        salary_to=salary_to,
        currency=item.get("salary_currency"),
        salary_period="monthly",
        city=city,
        remote=remote,
        work_format=work_format,
        employment_type=None,
        experience=map_experience(item.get("seniority") or item.get("grade")),
        published_at=parse_iso_datetime(item.get("published_at")),
        skills=skills,
        raw_data=item,
        source_metadata={"via": "api_offers", "offer_type": item.get("offer_type")},
    )


def parse_getmatch_page(url: str, html: str) -> VacancyData | None:
    vacancy_id_match = re.search(r"/vacancies/(\d+)", url)
    if not vacancy_id_match:
        return None
    source_id = vacancy_id_match.group(1)

    job = _extract_jobposting(html)
    og_desc = OG_DESC_RE.search(html)
    og_title = OG_TITLE_RE.search(html)
    description = (og_desc.group(1) if og_desc else None) or (job.get("description") if job else "") or ""
    title = (job.get("title") if job else None) or (og_title.group(1) if og_title else None)
    if title:
        title = re.sub(r"\s+[—\-]\s+getmatch.*$", "", title, flags=re.I).strip()
    if not title:
        return None

    org = (job.get("hiringOrganization") if job else None) or {}
    company = org.get("name") if isinstance(org, dict) else None
    if not company:
        company_match = COMPANY_RE.search(description)
        company = company_match.group(1).strip() if company_match else None

    salary = (job.get("baseSalary") if job else None) or {}
    value = salary.get("value") if isinstance(salary, dict) else {}
    if not isinstance(value, dict):
        value = {}
    salary_from = _int_money(value.get("minValue"))
    salary_to = _int_money(value.get("maxValue"))
    currency = salary.get("currency") if isinstance(salary, dict) else None
    if salary_from is None and salary_to is None:
        salary_from, salary_to, parsed_cur = _salary_from_text(description)
        currency = currency or parsed_cur

    remote = any(token in description.lower() for token in ("удалён", "удален", "remote"))
    city = None
    loc_match = re.search(r"Локации:\s*([^.]+)", description)
    if loc_match:
        city = loc_match.group(1).strip()
    work_format = map_work_format("remote" if remote else None, remote_flag=remote)

    grade = None
    html_l = html.lower()
    if "/junior" in html_l or "junior" in title.lower():
        grade = "junior"
    elif "/senior" in html_l or "senior" in title.lower():
        grade = "senior"
    elif "/lead" in html_l or "lead" in title.lower():
        grade = "lead"
    elif "/middle" in html_l or "middle" in title.lower():
        grade = "middle"

    skills: list[str] = []
    if job:
        raw_skills = job.get("skills") or job.get("knowsAbout") or []
        if isinstance(raw_skills, str):
            skills = [s.strip() for s in re.split(r"[,/]", raw_skills) if s.strip()]
        elif isinstance(raw_skills, list):
            skills = [str(s).strip() for s in raw_skills if str(s).strip()]

    return VacancyData(
        source=SourceName.GETMATCH,
        source_vacancy_id=source_id,
        url=url,
        title=title,
        company=company,
        description=description,
        salary_from=salary_from,
        salary_to=salary_to,
        currency=currency,
        salary_period="monthly",
        city=city,
        remote=remote,
        work_format=work_format,
        employment_type=(job.get("employmentType") if job else None),
        experience=map_experience(grade),
        published_at=parse_iso_datetime(job.get("datePosted") if job else None),
        skills=skills,
        raw_data=job or {"og": description},
        source_metadata={"via": "sitemap_jsonld" if job else "sitemap_og"},
    )


class GetMatchSource(VacancySource):
    name = SourceName.GETMATCH
    display_name = "GetMatch"
    auto_apply_supported = False

    async def fetch_vacancies(self, config: ParserConfig) -> list[VacancyData]:
        try:
            return await self._fetch_offers(config)
        except RuntimeError:
            return await self._fetch_sitemap(config)

    async def _fetch_offers(self, config: ParserConfig) -> list[VacancyData]:
        results: list[VacancyData] = []
        limit = min(max(config.per_page, 1), 50)
        max_items = 800
        headers = {**DEFAULT_HEADERS, "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=40.0, headers=headers, follow_redirects=True) as client:
            offset = 0
            page = 1
            while len(results) < max_items:
                try:
                    response = await client.get(
                        GETMATCH_OFFERS,
                        params={"offset": offset, "limit": limit, "p": page},
                    )
                except httpx.HTTPError as exc:
                    raise RuntimeError(f"GetMatch parser failed: offers network error — {exc}") from exc
                if response.status_code >= 400:
                    raise RuntimeError(
                        f"GetMatch parser failed: offers HTTP {response.status_code}: {response.text[:300]}"
                    )
                payload = response.json()
                offers = payload.get("offers") or []
                if not offers:
                    break
                results.extend(normalize_getmatch_offer(item) for item in offers)
                total = int((payload.get("meta") or {}).get("total") or 0)
                offset += limit
                page += 1
                if offset >= total or page > 30:
                    break
        return results

    async def _fetch_sitemap(self, config: ParserConfig) -> list[VacancyData]:
        limit = min(max(config.max_pages, 1) * 25, 80)
        headers = {**DEFAULT_HEADERS, "Accept": "text/html,application/xml;q=0.9"}
        async with httpx.AsyncClient(timeout=40.0, headers=headers, follow_redirects=True) as client:
            try:
                sitemap = await client.get(GETMATCH_SITEMAP)
            except httpx.HTTPError as exc:
                raise RuntimeError(f"GetMatch parser failed: sitemap network error — {exc}") from exc
            if sitemap.status_code >= 400:
                raise RuntimeError(f"GetMatch parser failed: sitemap HTTP {sitemap.status_code}")

            urls = filter_sitemap_urls(sitemap.text, config.query, limit)
            semaphore = asyncio.Semaphore(6)

            async def load(url: str) -> VacancyData | None:
                async with semaphore:
                    try:
                        response = await client.get(url)
                    except httpx.HTTPError:
                        return None
                    if response.status_code >= 400:
                        return None
                    return parse_getmatch_page(url, response.text)

            pages = await asyncio.gather(*(load(url) for url in urls))
        return [item for item in pages if item is not None]

    def health(self) -> dict:
        return {**super().health(), "status": "ready"}
