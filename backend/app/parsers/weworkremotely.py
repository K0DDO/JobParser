"""We Work Remotely RSS — programming category feed."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from app.core.enums import SourceName, WorkFormat
from app.parsers.base import ParserConfig, VacancySource
from app.parsers.http import DEFAULT_HEADERS
from app.schemas import VacancyData
from app.services.normalize import map_experience

WWR_RSS = "https://weworkremotely.com/categories/remote-programming-jobs.rss"
GUID_RE = re.compile(r"/(\d+)(?:-|$)")


def _text(el: ET.Element | None) -> str:
    if el is None or el.text is None:
        return ""
    return el.text.strip()


def normalize_wwr_item(item: dict[str, Any]) -> VacancyData:
    link = str(item.get("link") or "")
    m = GUID_RE.search(link) or GUID_RE.search(str(item.get("guid") or ""))
    vid = m.group(1) if m else link
    title_raw = str(item.get("title") or "Untitled")
    company = None
    title = title_raw
    if ":" in title_raw:
        company, title = [p.strip() for p in title_raw.split(":", 1)]
    published = None
    if item.get("pubDate"):
        try:
            published = parsedate_to_datetime(item["pubDate"]).replace(tzinfo=None)
        except (TypeError, ValueError, IndexError):
            published = None
    cats = [str(c) for c in (item.get("categories") or []) if c]
    return VacancyData(
        source=SourceName.WEWORKREMOTELY,
        source_vacancy_id=str(vid),
        url=link,
        title=title or title_raw,
        company=company,
        description=item.get("description"),
        city=item.get("region") or "Remote",
        remote=True,
        work_format=WorkFormat.REMOTE,
        experience=map_experience(None),
        published_at=published,
        skills=cats,
        raw_data=item,
    )


class WeWorkRemotelySource(VacancySource):
    name = SourceName.WEWORKREMOTELY
    display_name = "We Work Remotely"
    auto_apply_supported = False

    async def fetch_vacancies(self, config: ParserConfig) -> list[VacancyData]:
        query = (config.query or "").strip().lower()
        async with httpx.AsyncClient(timeout=45.0, headers=DEFAULT_HEADERS, follow_redirects=True) as client:
            try:
                response = await client.get(WWR_RSS)
            except httpx.HTTPError as exc:
                raise RuntimeError(f"WWR parser failed: network error — {exc}") from exc
            if response.status_code >= 400:
                raise RuntimeError(f"WWR parser failed: HTTP {response.status_code}")
            xml_text = response.text

        root = ET.fromstring(xml_text)
        channel = root.find("channel")
        if channel is None:
            return []
        results: list[VacancyData] = []
        for node in channel.findall("item"):
            cats = [_text(c) for c in node.findall("category") if _text(c)]
            region = next((c for c in cats if c.lower() not in {"programming", "full-time", "contract"}), None)
            item = {
                "title": _text(node.find("title")),
                "link": _text(node.find("link")),
                "description": _text(node.find("description")),
                "pubDate": _text(node.find("pubDate")),
                "guid": _text(node.find("guid")),
                "categories": cats,
                "region": region,
            }
            data = normalize_wwr_item(item)
            if query:
                blob = f"{data.title} {data.company or ''} {' '.join(data.skills)}".lower()
                if query not in blob:
                    continue
            results.append(data)
            if len(results) >= config.max_pages * config.per_page:
                break
        return results
