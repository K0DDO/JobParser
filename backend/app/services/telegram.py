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


async def _telegram_post(method: str, data: dict[str, Any], files: dict | None = None) -> dict[str, Any]:
    if not telegram_configured():
        raise RuntimeError("Telegram is not configured")
    url = f"{TELEGRAM_API}/bot{settings.telegram_bot_token}/{method}"
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(url, data=data, files=files)
        body = response.json() if response.content else {}
        if response.status_code >= 400 or not body.get("ok"):
            detail = body.get("description") or response.text[:400]
            raise RuntimeError(f"Telegram {method} failed: {detail}")
        return body


async def send_message(text: str, *, parse_mode: str = "HTML") -> dict[str, Any]:
    data = {
        "chat_id": str(settings.telegram_chat_id).strip(),
        "text": text[:4096],
        "disable_web_page_preview": "true",
    }
    if parse_mode:
        data["parse_mode"] = parse_mode
    return await _telegram_post("sendMessage", data)


async def send_photo_bytes(
    *,
    photo: bytes,
    caption: str,
    filename: str = "vacancy.png",
) -> dict[str, Any]:
    data = {
        "chat_id": str(settings.telegram_chat_id).strip(),
        "caption": caption[:1024],
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }
    files = {"photo": (filename, photo, "image/png")}
    return await _telegram_post("sendPhoto", data, files=files)


async def notify_startup() -> bool:
    """Ping the chat when backend boots and show filter buttons."""
    if not telegram_configured():
        return False
    try:
        from app.services.telegram_bot import send_filters_menu

        await send_message(
            "<b>JobParser запущен</b>\n"
            "Синк активен.\n"
            "Фильтры: сначала <b>область</b> (Backend / Frontend / Анализ…), "
            "потом <b>стек</b> (язык + фреймворки), затем остальное.\n"
            "Без области рассылка выключена. /filters"
        )
        await send_filters_menu()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("Telegram startup notify failed: %s", exc)
        return False


async def send_vacancy_card(
    vacancy: Vacancy,
    *,
    profile_name: str | None = None,
    force: bool = False,
) -> bool:
    """Render and send one vacancy card. Returns True on success."""
    if not telegram_configured():
        return False
    if not force and vacancy.telegram_notified_at is not None:
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
