"""Outbound Telegram vacancy cards (sendPhoto)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.timeutil import utc_now_naive
from app.models import Vacancy
from app.services.telegram_cards import build_caption, render_banner_png

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"
SEND_GAP_SECONDS = 1.05


def telegram_configured() -> bool:
    return bool(
        settings.telegram_enabled
        and settings.telegram_bot_token.strip()
        and str(settings.telegram_chat_id).strip()
    )


async def send_photo_bytes(
    *,
    photo: bytes,
    caption: str,
    filename: str = "vacancy.png",
) -> dict[str, Any]:
    if not telegram_configured():
        raise RuntimeError("Telegram is not configured")
    url = f"{TELEGRAM_API}/bot{settings.telegram_bot_token}/sendPhoto"
    data = {
        "chat_id": str(settings.telegram_chat_id).strip(),
        "caption": caption[:1024],
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }
    files = {"photo": (filename, photo, "image/png")}
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(url, data=data, files=files)
        body = response.json() if response.content else {}
        if response.status_code >= 400 or not body.get("ok"):
            detail = body.get("description") or response.text[:400]
            raise RuntimeError(f"Telegram sendPhoto failed: {detail}")
        return body


async def send_vacancy_card(
    vacancy: Vacancy,
    *,
    profile_name: str | None = None,
) -> bool:
    """Render and send one vacancy card. Returns True on success."""
    if not telegram_configured():
        return False
    if vacancy.telegram_notified_at is not None:
        return False
    caption = build_caption(vacancy, profile_name=profile_name)
    photo = render_banner_png(vacancy)
    await send_photo_bytes(photo=photo, caption=caption, filename=f"vacancy_{vacancy.id}.png")
    return True


async def notify_new_matched_vacancies(
    session: AsyncSession,
    items: list[tuple[Vacancy, str | None]],
) -> int:
    """
    Send cards for (vacancy, profile_name) pairs.
    Marks telegram_notified_at after each successful send.
    """
    if not telegram_configured() or not items:
        return 0
    sent = 0
    for index, (vacancy, profile_name) in enumerate(items):
        if vacancy.telegram_notified_at is not None:
            continue
        try:
            ok = await send_vacancy_card(vacancy, profile_name=profile_name)
            if ok:
                vacancy.telegram_notified_at = utc_now_naive()
                sent += 1
                await session.flush()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Telegram notify failed for vacancy %s: %s",
                vacancy.id,
                exc,
            )
        if index + 1 < len(items):
            await asyncio.sleep(SEND_GAP_SECONDS)
    return sent
