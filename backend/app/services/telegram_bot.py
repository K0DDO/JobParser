"""Telegram long-polling bot: multi-step filter wizard + commands."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import httpx
from sqlalchemy import select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models import Vacancy
from app.services.settings_service import get_or_create_settings
from app.services.telegram import send_message, telegram_configured
from app.services.telegram_cards import build_caption, render_banner_png
from app.services.telegram_filters import (
    TELEGRAM_AGE_HOURS,
    TELEGRAM_CITIES,
    TELEGRAM_COMPANIES,
    TELEGRAM_EMPLOYMENT,
    TELEGRAM_EXPERIENCES,
    TELEGRAM_FRAMEWORKS,
    TELEGRAM_LANGUAGES,
    TELEGRAM_PORTALS,
    TELEGRAM_ROLES,
    TELEGRAM_SALARY_FROM,
    TELEGRAM_SALARY_TO,
    TELEGRAM_WORK_FORMATS,
    empty_filters,
    format_filters_summary,
    load_filters_from_settings,
    save_filters_to_settings,
    vacancy_matches_telegram_filters,
)

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"
_poll_task: asyncio.Task | None = None
_stop = asyncio.Event()

ROLE_KEYS = {k for k, _ in TELEGRAM_ROLES}
STACK_KEYS = set(TELEGRAM_LANGUAGES + TELEGRAM_FRAMEWORKS)
FMT_KEYS = {k for k, _ in TELEGRAM_WORK_FORMATS}
EXP_KEYS = {k for k, _ in TELEGRAM_EXPERIENCES}
PORTAL_KEYS = {k for k, _ in TELEGRAM_PORTALS}
COMPANY_KEYS = {q for q, _ in TELEGRAM_COMPANIES}
EMPL_KEYS = {k for k, _ in TELEGRAM_EMPLOYMENT}
CITY_KEYS = set(TELEGRAM_CITIES)


def _allowed_chat(chat_id: Any) -> bool:
    expected = str(settings.telegram_chat_id).strip()
    return bool(expected) and str(chat_id) == expected


def _btn(text: str, data: str) -> dict[str, str]:
    return {"text": text[:64], "callback_data": data[:64]}


def _rows_of(items: list[dict[str, str]], per_row: int = 2) -> list[list[dict[str, str]]]:
    rows: list[list[dict[str, str]]] = []
    row: list[dict[str, str]] = []
    for item in items:
        row.append(item)
        if len(row) >= per_row:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows


def _toggle(items: list[str], value: str) -> list[str]:
    out = list(items)
    key = value.lower()
    if any(x.lower() == key for x in out):
        return [x for x in out if x.lower() != key]
    out.append(value)
    return out


def _mark(selected: bool, label: str) -> str:
    return f"{'✅ ' if selected else ''}{label}"


def _nav_footer(*extra: list[dict[str, str]]) -> list[list[dict[str, str]]]:
    rows = list(extra)
    rows.append(
        [
            _btn("⬅️ Меню", "m:main"),
            _btn("🧪 Тест", "cmd:test"),
        ]
    )
    return rows


def _main_keyboard(filters: dict[str, Any]) -> dict[str, Any]:
    roles_n = len(filters["roles"])
    skills_n = len(filters["skills"])
    rows = [
        [_btn(f"1️⃣ Область ({roles_n})", "m:roles")],
        [
            _btn(
                f"2️⃣ Языки ({sum(1 for s in filters['skills'] if s in TELEGRAM_LANGUAGES)})",
                "m:langs",
            ),
            _btn(
                f"2️⃣ Фреймворки ({sum(1 for s in filters['skills'] if s in TELEGRAM_FRAMEWORKS)})",
                "m:fw",
            ),
        ],
        [
            _btn(f"Формат ({len(filters['work_formats'])})", "m:format"),
            _btn(f"Опыт ({len(filters['experiences'])})", "m:exp"),
        ],
        [
            _btn("Зарплата", "m:salary"),
            _btn(f"Порталы ({len(filters['sources'])})", "m:portal"),
        ],
        [
            _btn(f"Компании ({len(filters['companies'])})", "m:company"),
            _btn(f"Города ({len(filters['cities'])})", "m:city"),
        ],
        [
            _btn(f"Занятость ({len(filters['employment_types'])})", "m:empl"),
            _btn("Период", "m:age"),
        ],
        [
            _btn("🧹 Сбросить всё", "c:all"),
            _btn("🧪 Тестовая вакансия", "cmd:test"),
        ],
    ]
    return {"inline_keyboard": rows}


def _roles_keyboard(filters: dict[str, Any]) -> dict[str, Any]:
    selected = {r.lower() for r in filters["roles"]}
    buttons = [
        _btn(_mark(key.lower() in selected, label), f"t:r:{key}")
        for key, label in TELEGRAM_ROLES
    ]
    rows = _rows_of(buttons, 2)
    rows.append([_btn("🧹 Сбросить область", "c:roles"), _btn("➡️ К языкам", "m:langs")])
    rows.extend(_nav_footer())
    return {"inline_keyboard": rows}


def _langs_keyboard(filters: dict[str, Any]) -> dict[str, Any]:
    selected = {s.lower() for s in filters["skills"]}
    buttons = [
        _btn(_mark(lang.lower() in selected, lang), f"t:sk:{lang}")
        for lang in TELEGRAM_LANGUAGES
    ]
    rows = _rows_of(buttons, 3)
    rows.append(
        [
            _btn("🧹 Сбросить языки", "c:langs"),
            _btn("➡️ Фреймворки", "m:fw"),
        ]
    )
    rows.extend(_nav_footer())
    return {"inline_keyboard": rows}


def _fw_keyboard(filters: dict[str, Any]) -> dict[str, Any]:
    selected = {s.lower() for s in filters["skills"]}
    buttons = [
        _btn(_mark(fw.lower() in selected, fw), f"t:sk:{fw}")
        for fw in TELEGRAM_FRAMEWORKS
    ]
    rows = _rows_of(buttons, 2)
    rows.append(
        [
            _btn("🧹 Сбросить фреймворки", "c:fw"),
            _btn("➡️ Формат", "m:format"),
        ]
    )
    rows.extend(_nav_footer())
    return {"inline_keyboard": rows}


def _format_keyboard(filters: dict[str, Any]) -> dict[str, Any]:
    selected = {x.lower() for x in filters["work_formats"]}
    buttons = [
        _btn(_mark(key.lower() in selected, label), f"t:fmt:{key}")
        for key, label in TELEGRAM_WORK_FORMATS
    ]
    rows = _rows_of(buttons, 3)
    rows.append([_btn("🧹 Сбросить формат", "c:format")])
    rows.extend(_nav_footer())
    return {"inline_keyboard": rows}


def _exp_keyboard(filters: dict[str, Any]) -> dict[str, Any]:
    selected = set(filters["experiences"])
    buttons = [
        _btn(_mark(key in selected, label), f"t:exp:{key}")
        for key, label in TELEGRAM_EXPERIENCES
    ]
    rows = _rows_of(buttons, 2)
    rows.append([_btn("🧹 Сбросить опыт", "c:exp")])
    rows.extend(_nav_footer())
    return {"inline_keyboard": rows}


def _salary_keyboard(filters: dict[str, Any]) -> dict[str, Any]:
    from_v = filters.get("salary_from")
    to_v = filters.get("salary_to")
    has = filters.get("has_salary")
    rows: list[list[dict[str, str]]] = [[_btn("── от ₽ / мес ──", "noop")]]
    rows.extend(
        _rows_of(
            [
                _btn(_mark(from_v == n, f"от {n // 1000}к"), f"s:from:{n}")
                for n in TELEGRAM_SALARY_FROM
            ],
            3,
        )
    )
    rows.append([_btn("── до ₽ / мес ──", "noop")])
    rows.extend(
        _rows_of(
            [
                _btn(_mark(to_v == n, f"до {n // 1000}к"), f"s:to:{n}")
                for n in TELEGRAM_SALARY_TO
            ],
            3,
        )
    )
    rows.append(
        [
            _btn(_mark(has is True, "Только с вилкой"), "s:has:1"),
            _btn(_mark(has is False, "Без вилки"), "s:has:0"),
        ]
    )
    rows.append([_btn("🧹 Сбросить зарплату", "c:salary")])
    rows.extend(_nav_footer())
    return {"inline_keyboard": rows}


def _portal_keyboard(filters: dict[str, Any]) -> dict[str, Any]:
    selected = {s.lower() for s in filters["sources"]}
    buttons = [
        _btn(_mark(key.lower() in selected, label), f"t:src:{key}")
        for key, label in TELEGRAM_PORTALS
    ]
    rows = _rows_of(buttons, 3)
    rows.append([_btn("🧹 Все порталы", "c:portal")])
    rows.extend(_nav_footer())
    return {"inline_keyboard": rows}


def _company_keyboard(filters: dict[str, Any]) -> dict[str, Any]:
    selected = {c.lower() for c in filters["companies"]}
    buttons = [
        _btn(_mark(query.lower() in selected, label), f"t:co:{query}")
        for query, label in TELEGRAM_COMPANIES
    ]
    rows = _rows_of(buttons, 2)
    rows.append([_btn("🧹 Все компании", "c:company")])
    rows.extend(_nav_footer())
    return {"inline_keyboard": rows}


def _city_keyboard(filters: dict[str, Any]) -> dict[str, Any]:
    selected = {c.lower() for c in filters["cities"]}
    buttons = [
        _btn(_mark(city.lower() in selected, city), f"t:ci:{city}")
        for city in TELEGRAM_CITIES
    ]
    rows = _rows_of(buttons, 2)
    rows.append([_btn("🧹 Все города", "c:city")])
    rows.extend(_nav_footer())
    return {"inline_keyboard": rows}


def _empl_keyboard(filters: dict[str, Any]) -> dict[str, Any]:
    selected = {e.lower() for e in filters["employment_types"]}
    buttons = [
        _btn(_mark(key.lower() in selected, label), f"t:em:{key}")
        for key, label in TELEGRAM_EMPLOYMENT
    ]
    rows = _rows_of(buttons, 2)
    rows.append([_btn("🧹 Любая занятость", "c:empl")])
    rows.extend(_nav_footer())
    return {"inline_keyboard": rows}


def _age_keyboard(filters: dict[str, Any]) -> dict[str, Any]:
    current = filters.get("max_age_hours")
    buttons = [
        _btn(_mark(current == hours, label), f"s:age:{hours}")
        for hours, label in TELEGRAM_AGE_HOURS
    ]
    rows = _rows_of(buttons, 3)
    rows.append(
        [
            _btn(_mark(current is None, "любой"), "s:age:0"),
            _btn("🧹 Сброс периода", "c:age"),
        ]
    )
    rows.extend(_nav_footer())
    return {"inline_keyboard": rows}


def _keyboard_for(menu: str, filters: dict[str, Any]) -> dict[str, Any]:
    return {
        "main": _main_keyboard,
        "roles": _roles_keyboard,
        "langs": _langs_keyboard,
        "fw": _fw_keyboard,
        "format": _format_keyboard,
        "exp": _exp_keyboard,
        "salary": _salary_keyboard,
        "portal": _portal_keyboard,
        "company": _company_keyboard,
        "city": _city_keyboard,
        "empl": _empl_keyboard,
        "age": _age_keyboard,
    }.get(menu, _main_keyboard)(filters)


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
        "text": text[:4096],
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


async def _show_menu(
    chat_id: str,
    filters: dict[str, Any],
    menu: str = "main",
    message_id: int | None = None,
) -> None:
    await _edit_or_send(
        chat_id,
        format_filters_summary(filters),
        _keyboard_for(menu, filters),
        message_id=message_id,
    )


async def _send_test_card(chat_id: str) -> None:
    async with AsyncSessionLocal() as session:
        app_settings = await get_or_create_settings(session)
        filters = load_filters_from_settings(app_settings)
        result = await session.execute(select(Vacancy).order_by(Vacancy.id.desc()).limit(80))
        vacancies = list(result.scalars().all())
        chosen: Vacancy | None = None
        for vac in vacancies:
            if vacancy_matches_telegram_filters(vac, filters):
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


def _apply_clear(filters: dict[str, Any], what: str) -> dict[str, Any]:
    if what == "all":
        return empty_filters()
    if what == "roles":
        filters["roles"] = []
    elif what == "langs":
        filters["skills"] = [s for s in filters["skills"] if s not in TELEGRAM_LANGUAGES]
    elif what == "fw":
        filters["skills"] = [s for s in filters["skills"] if s not in TELEGRAM_FRAMEWORKS]
    elif what == "format":
        filters["work_formats"] = []
    elif what == "exp":
        filters["experiences"] = []
    elif what == "salary":
        filters["salary_from"] = None
        filters["salary_to"] = None
        filters["has_salary"] = None
    elif what == "portal":
        filters["sources"] = []
    elif what == "company":
        filters["companies"] = []
    elif what == "city":
        filters["cities"] = []
    elif what == "empl":
        filters["employment_types"] = []
    elif what == "age":
        filters["max_age_hours"] = None
    return filters


def _menu_after_clear(what: str) -> str:
    return {
        "roles": "roles",
        "langs": "langs",
        "fw": "fw",
        "format": "format",
        "exp": "exp",
        "salary": "salary",
        "portal": "portal",
        "company": "company",
        "city": "city",
        "empl": "empl",
        "age": "age",
        "all": "main",
    }.get(what, "main")


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
    if data == "noop":
        await _answer_callback(callback_id)
        return

    async with AsyncSessionLocal() as session:
        app_settings = await get_or_create_settings(session)
        filters = load_filters_from_settings(app_settings)
        menu = "main"
        toast = ""

        if data.startswith("m:"):
            menu = data.split(":", 1)[1] or "main"
            await _answer_callback(callback_id)
            await _show_menu(chat_id, filters, menu, message_id=message_id)
            return

        if data == "cmd:test":
            await _answer_callback(callback_id, "Шлю тест…")
            await _send_test_card(chat_id)
            return

        if data.startswith("c:"):
            what = data.split(":", 1)[1]
            filters = _apply_clear(filters, what)
            save_filters_to_settings(app_settings, filters)
            await session.commit()
            await _answer_callback(callback_id, "Сброшено")
            await _show_menu(chat_id, filters, _menu_after_clear(what), message_id=message_id)
            return

        changed = True
        if data.startswith("t:r:"):
            role = data[4:]
            if role not in ROLE_KEYS:
                changed = False
            else:
                filters["roles"] = _toggle(filters["roles"], role)
                toast, menu = role, "roles"
        elif data.startswith("t:sk:"):
            skill = data[5:]
            if skill not in STACK_KEYS:
                changed = False
            else:
                filters["skills"] = _toggle(filters["skills"], skill)
                toast = skill
                menu = "langs" if skill in TELEGRAM_LANGUAGES else "fw"
        elif data.startswith("t:fmt:"):
            fmt = data[6:]
            if fmt not in FMT_KEYS:
                changed = False
            else:
                filters["work_formats"] = _toggle(filters["work_formats"], fmt)
                toast, menu = fmt, "format"
        elif data.startswith("t:exp:"):
            exp = data[6:]
            if exp not in EXP_KEYS:
                changed = False
            else:
                filters["experiences"] = _toggle(filters["experiences"], exp)
                toast, menu = exp, "exp"
        elif data.startswith("t:src:"):
            src = data[6:]
            if src not in PORTAL_KEYS:
                changed = False
            else:
                filters["sources"] = _toggle(filters["sources"], src)
                toast, menu = src, "portal"
        elif data.startswith("t:co:"):
            company = data[5:]
            if company not in COMPANY_KEYS:
                changed = False
            else:
                filters["companies"] = _toggle(filters["companies"], company)
                toast, menu = company, "company"
        elif data.startswith("t:ci:"):
            city = data[5:]
            if city not in CITY_KEYS:
                changed = False
            else:
                filters["cities"] = _toggle(filters["cities"], city)
                toast, menu = city, "city"
        elif data.startswith("t:em:"):
            empl = data[5:]
            if empl not in EMPL_KEYS:
                changed = False
            else:
                filters["employment_types"] = _toggle(filters["employment_types"], empl)
                toast, menu = empl, "empl"
        elif data.startswith("s:from:"):
            value = int(data.split(":")[-1])
            filters["salary_from"] = None if filters.get("salary_from") == value else value
            toast, menu = f"от {value}", "salary"
        elif data.startswith("s:to:"):
            value = int(data.split(":")[-1])
            filters["salary_to"] = None if filters.get("salary_to") == value else value
            toast, menu = f"до {value}", "salary"
        elif data.startswith("s:has:"):
            flag = data.endswith(":1")
            filters["has_salary"] = None if filters.get("has_salary") is flag else flag
            toast, menu = "вилка", "salary"
        elif data.startswith("s:age:"):
            hours = int(data.split(":")[-1])
            if hours == 0:
                filters["max_age_hours"] = None
            elif filters.get("max_age_hours") == hours:
                filters["max_age_hours"] = None
            else:
                filters["max_age_hours"] = hours
            toast, menu = "период", "age"
        else:
            await _answer_callback(callback_id)
            return

        if not changed:
            await _answer_callback(callback_id)
            return

        save_filters_to_settings(app_settings, filters)
        await session.commit()
        await _answer_callback(callback_id, toast)
        await _show_menu(chat_id, filters, menu, message_id=message_id)


async def _handle_message(message: dict[str, Any]) -> None:
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id") or "")
    if not _allowed_chat(chat_id):
        return
    text = str(message.get("text") or "").strip()
    cmd = text.split()[0].split("@")[0].lower() if text else ""

    async with AsyncSessionLocal() as session:
        app_settings = await get_or_create_settings(session)
        filters = load_filters_from_settings(app_settings)

        if cmd in {"/start", "/filters", "/menu"}:
            await _show_menu(chat_id, filters, "main")
            return

        if cmd == "/status":
            await send_message(format_filters_summary(filters))
            return

        if cmd == "/reset":
            filters = empty_filters()
            save_filters_to_settings(app_settings, filters)
            await session.commit()
            await _show_menu(chat_id, filters, "main")
            return

        if cmd == "/test":
            await _send_test_card(chat_id)
            return

        if text.startswith("/"):
            await send_message(
                "Команды:\n"
                "/filters — мастер фильтров\n"
                "/status — текущий выбор\n"
                "/test — тестовая карточка\n"
                "/reset — сбросить всё"
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
    if not telegram_configured():
        return False
    async with AsyncSessionLocal() as session:
        app_settings = await get_or_create_settings(session)
        filters = load_filters_from_settings(app_settings)
        await _show_menu(str(settings.telegram_chat_id).strip(), filters, "main")
    return True
