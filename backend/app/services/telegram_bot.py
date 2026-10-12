"""Telegram long-polling bot: filter buttons + commands."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx
from sqlalchemy import select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models import AppSettings, Vacancy
from app.services.telegram import send_message, telegram_configured
from app.services.telegram_cards import build_caption, render_banner_png
from app.services.telegram_filters import (
    TELEGRAM_ROLES,
    TELEGRAM_WORK_FORMATS,
    vacancy_matches_telegram_filters,
)
from app.services.settings_service import get_or_create_settings

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"
_poll_task: asyncio.Task | None = None
_stop = asyncio.Event()


def _allowed_chat(chat_id: Any) -> bool:
    expected = str(settings.telegram_chat_id).strip()
    return expected and str(chat_id) == expected


def _roles_keyboard(selected: list[str]) -> dict[str, Any]:
    selected_set = {r.lower() for r in selected}
    rows: list[list[dict[str, str]]] = []
    row: list[dict[str, str]] = []
    for role in TELEGRAM_ROLES:
        mark = "✅ " if role.lower() in selected_set else ""
        row.append(
            {
                "text": f"{mark}{role}",
                "callback_data": f"role:{role}",
            }
        )
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append(
        [
            {"text": "🧹 Сбросить роли", "callback_data": "roles:clear"},
            {"text": "📦 Формат работы", "callback_data": "menu:formats"},
        ]
    )
    rows.append([{"text": "🧪 Тестовая вакансия", "callback_data": "cmd:test"}])
    return {"inline_keyboard": rows}


def _formats_keyboard(selected: list[str]) -> dict[str, Any]:
    selected_set = {f.lower() for f in selected}
    rows: list[list[dict[str, str]]] = []
    row: list[dict[str, str]] = []
    for key, label in TELEGRAM_WORK_FORMATS:
        mark = "✅ " if key.lower() in selected_set else ""
        row.append(
            {
                "text": f"{mark}{label}",
                "callback_data": f"fmt:{key}",
            }
        )
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append(
        [
            {"text": "🧹 Сбросить формат", "callback_data": "formats:clear"},
            {"text": "💼 Профессии", "callback_data": "menu:roles"},
        ]
    )
    return {"inline_keyboard": rows}


def _status_text(app_settings: AppSettings) -> str:
    roles = app_settings.telegram_roles or []
    formats = app_settings.telegram_work_formats or []
    fmt_labels = {
        key: label for key, label in TELEGRAM_WORK_FORMATS
    }
    roles_line = ", ".join(roles) if roles else "не выбраны (рассылка выкл)"
    formats_line = (
        ", ".join(fmt_labels.get(f, f) for f in formats)
        if formats
        else "любой"
    )
    return (
        "<b>Фильтры Telegram</b>\n"
        f"Профессии: <b>{roles_line}</b>\n"
        f"Формат: <b>{formats_line}</b>\n\n"
        "Жми кнопки ниже — включи нужные профессии.\n"
        "Команды: /filters · /test · /status"
    )


async def _api(
    method: str,
    data: dict[str, Any] | None = None,
    *,
    files: dict | None = None,
) -> dict[str, Any]:
    url = f"{TELEGRAM_API}/bot{settings.telegram_bot_token}/{method}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, data=data or {}, files=files)
        body = response.json() if response.content else {}
        if not body.get("ok"):
            detail = body.get("description") or response.text[:300]
            raise RuntimeError(f"Telegram {method}: {detail}")
        return body


async def _answer_callback(callback_id: str, text: str = "") -> None:
    try:
        await _api(
            "answerCallbackQuery",
            {"callback_query_id": callback_id, "text": text[:180]},
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("answerCallbackQuery failed: %s", exc)


async def _edit_or_send(
    chat_id: str,
    text: str,
    reply_markup: dict[str, Any],
    message_id: int | None = None,
) -> None:
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": json.dumps(reply_markup, ensure_ascii=False),
        "disable_web_page_preview": "true",
    }
    if message_id is not None:
        payload["message_id"] = str(message_id)
        try:
            await _api("editMessageText", payload)
            return
        except Exception:  # noqa: BLE001
            pass
    await _api("sendMessage", payload)


async def _toggle_list(current: list[str] | None, value: str) -> list[str]:
    items = list(current or [])
    lower = {x.lower(): x for x in items}
    key = value.lower()
    if key in lower:
        items = [x for x in items if x.lower() != key]
    else:
        items.append(value)
    return items


async def _send_test_card(chat_id: str) -> None:
    async with AsyncSessionLocal() as session:
        app_settings = await get_or_create_settings(session)
        result = await session.execute(
            select(Vacancy).order_by(Vacancy.id.desc()).limit(40)
        )
        vacancies = list(result.scalars().all())
        chosen: Vacancy | None = None
        for vac in vacancies:
            if vacancy_matches_telegram_filters(
                vac,
                roles=app_settings.telegram_roles,
                work_formats=app_settings.telegram_work_formats,
            ):
                chosen = vac
                break
        if chosen is None and vacancies:
            chosen = vacancies[0]
        if chosen is None:
            await send_message(
                "В базе пока нет вакансий. Запусти синк в приложении, потом /test."
            )
            return
        caption = build_caption(chosen, profile_name="тест")
        photo = render_banner_png(chosen)
        # force path: send without marking notified if already notified
        data = {
            "chat_id": chat_id,
            "caption": caption[:1024],
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }
        files = {"photo": (f"vacancy_{chosen.id}.png", photo, "image/png")}
        await _api("sendPhoto", data, files=files)
        await send_message(
            f"Тест: <b>{chosen.title}</b>\n"
            f"id={chosen.id} · {chosen.source or '?'}"
        )


async def _handle_callback(callback: dict[str, Any]) -> None:
    data = str(callback.get("data") or "")
    message = callback.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id") or "")
    message_id = message.get("message_id")
    callback_id = str(callback.get("id") or "")
    if not _allowed_chat(chat_id):
        await _answer_callback(callback_id, "Чат не привязан")
        return

    async with AsyncSessionLocal() as session:
        app_settings = await get_or_create_settings(session)
        roles = list(app_settings.telegram_roles or [])
        formats = list(app_settings.telegram_work_formats or [])

        if data.startswith("role:"):
            role = data.split(":", 1)[1]
            if role in TELEGRAM_ROLES:
                roles = await _toggle_list(roles, role)
                app_settings.telegram_roles = roles
                await session.commit()
                await _answer_callback(callback_id, f"{role}")
                await _edit_or_send(
                    chat_id,
                    _status_text(app_settings),
                    _roles_keyboard(roles),
                    message_id=message_id,
                )
            return

        if data.startswith("fmt:"):
            fmt = data.split(":", 1)[1]
            keys = {k for k, _ in TELEGRAM_WORK_FORMATS}
            if fmt in keys:
                formats = await _toggle_list(formats, fmt)
                app_settings.telegram_work_formats = formats
                await session.commit()
                await _answer_callback(callback_id, fmt)
                await _edit_or_send(
                    chat_id,
                    _status_text(app_settings),
                    _formats_keyboard(formats),
                    message_id=message_id,
                )
            return

        if data == "roles:clear":
            app_settings.telegram_roles = []
            await session.commit()
            await _answer_callback(callback_id, "Роли сброшены")
            await _edit_or_send(
                chat_id,
                _status_text(app_settings),
                _roles_keyboard([]),
                message_id=message_id,
            )
            return

        if data == "formats:clear":
            app_settings.telegram_work_formats = []
            await session.commit()
            await _answer_callback(callback_id, "Формат сброшен")
            await _edit_or_send(
                chat_id,
                _status_text(app_settings),
                _formats_keyboard([]),
                message_id=message_id,
            )
            return

        if data == "menu:roles":
            await _answer_callback(callback_id)
            await _edit_or_send(
                chat_id,
                _status_text(app_settings),
                _roles_keyboard(roles),
                message_id=message_id,
            )
            return

        if data == "menu:formats":
            await _answer_callback(callback_id)
            await _edit_or_send(
                chat_id,
                _status_text(app_settings),
                _formats_keyboard(formats),
                message_id=message_id,
            )
            return

        if data == "cmd:test":
            await _answer_callback(callback_id, "Шлю тест…")
            await _send_test_card(chat_id)
            return

        await _answer_callback(callback_id)


async def _handle_message(message: dict[str, Any]) -> None:
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id") or "")
    if not _allowed_chat(chat_id):
        return
    text = str(message.get("text") or "").strip()
    cmd = text.split()[0].split("@")[0].lower() if text else ""

    async with AsyncSessionLocal() as session:
        app_settings = await get_or_create_settings(session)
        roles = list(app_settings.telegram_roles or [])
        formats = list(app_settings.telegram_work_formats or [])

        if cmd in {"/start", "/filters", "/menu"}:
            await _edit_or_send(
                chat_id,
                _status_text(app_settings),
                _roles_keyboard(roles),
            )
            return

        if cmd == "/formats":
            await _edit_or_send(
                chat_id,
                _status_text(app_settings),
                _formats_keyboard(formats),
            )
            return

        if cmd == "/status":
            await send_message(_status_text(app_settings))
            return

        if cmd == "/test":
            await _send_test_card(chat_id)
            return

        if text.startswith("/"):
            await send_message(
                "Команды:\n"
                "/filters — кнопки профессий\n"
                "/formats — формат работы\n"
                "/test — тестовая карточка\n"
                "/status — текущий выбор"
            )


async def _process_update(update: dict[str, Any]) -> None:
    if "callback_query" in update:
        await _handle_callback(update["callback_query"])
        return
    if "message" in update:
        await _handle_message(update["message"])


async def _poll_loop() -> None:
    if not telegram_configured():
        logger.info("Telegram bot poller skipped (not configured)")
        return
    offset = 0
    logger.info("Telegram bot poller started")
    # Drop pending updates so we don't replay old /start spam
    try:
        body = await _api("getUpdates", {"offset": -1, "timeout": "0"})
        results = body.get("result") or []
        if results:
            offset = int(results[-1]["update_id"]) + 1
    except Exception as exc:  # noqa: BLE001
        logger.warning("Telegram getUpdates bootstrap failed: %s", exc)

    while not _stop.is_set():
        try:
            body = await _api(
                "getUpdates",
                {
                    "offset": str(offset),
                    "timeout": "25",
                    "allowed_updates": json.dumps(["message", "callback_query"]),
                },
            )
            for update in body.get("result") or []:
                offset = max(offset, int(update["update_id"]) + 1)
                try:
                    await _process_update(update)
                except Exception:  # noqa: BLE001
                    logger.exception("Telegram update handler failed")
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("Telegram poll error: %s", exc)
            await asyncio.sleep(3)


def start_telegram_bot() -> None:
    global _poll_task
    if not telegram_configured():
        return
    if _poll_task and not _poll_task.done():
        return
    _stop.clear()
    _poll_task = asyncio.create_task(_poll_loop(), name="telegram-bot-poller")


async def stop_telegram_bot() -> None:
    global _poll_task
    _stop.set()
    if _poll_task and not _poll_task.done():
        _poll_task.cancel()
        try:
            await _poll_task
        except asyncio.CancelledError:
            pass
    _poll_task = None


async def send_filters_menu() -> bool:
    """Push filter keyboard to the bound chat (startup / after deploy)."""
    if not telegram_configured():
        return False
    async with AsyncSessionLocal() as session:
        app_settings = await get_or_create_settings(session)
        roles = list(app_settings.telegram_roles or [])
        await _edit_or_send(
            str(settings.telegram_chat_id).strip(),
            _status_text(app_settings),
            _roles_keyboard(roles),
        )
    return True
