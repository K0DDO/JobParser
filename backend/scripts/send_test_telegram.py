"""One-off: send a demo vacancy card to the bound Telegram chat."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

env_path = ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())

from app.services.telegram import send_message, send_photo_bytes  # noqa: E402
from app.services.telegram_cards import build_caption, render_banner_png  # noqa: E402


async def main() -> None:
    vac = SimpleNamespace(
        id=0,
        title="Python Backend Developer (тест)",
        company="JobParser Demo",
        source="hh",
        city="Москва",
        remote=True,
        work_format="remote",
        salary_from=250000,
        salary_to=350000,
        currency="RUB",
        salary_period="month",
        url="https://hh.ru/vacancy/0",
        skills=["Python", "FastAPI", "Postgres"],
        experience="middle",
        description="Тестовая вакансия для проверки Telegram-карточки",
        published_at=None,
    )
    caption = build_caption(vac, profile_name="тест")
    photo = render_banner_png(vac)
    await send_message(
        "<b>Тест фильтров</b>\n"
        "Ниже демо-карточка Backend.\n"
        "После деплоя напиши боту /filters — кнопки профессий."
    )
    await send_photo_bytes(photo=photo, caption=caption, filename="test_vacancy.png")
    print("sent ok")


if __name__ == "__main__":
    asyncio.run(main())
