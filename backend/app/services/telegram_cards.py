"""GetMatch-style vacancy cards: HTML caption + pastel rose PNG banner."""

from __future__ import annotations

import html
import re
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from app.services.currency import salary_in_rub

BANNER_W = 1200
BANNER_H = 630

BG_TOP = (246, 213, 216)  # #F6D5D8
BG_BOTTOM = (240, 196, 204)  # #F0C4CC
TEXT_DARK = (92, 36, 48)  # #5C2430
TEXT_ACCENT = (139, 58, 74)  # #8B3A4A
TEXT_SECONDARY = (107, 63, 72)  # #6B3F48
LOGO_BG = (255, 255, 255, 230)

_LOGO_DIR = Path(__file__).resolve().parent.parent / "assets" / "logos"

_COMPANY_LOGO_ALIASES: dict[str, str] = {
    "альфа": "alfa-bank.png",
    "alfa": "alfa-bank.png",
    "сбер": "sber.png",
    "sber": "sber.png",
    "яндекс": "yandex.png",
    "yandex": "yandex.png",
    "тинькофф": "tinkoff.png",
    "tinkoff": "tinkoff.png",
    "т-банк": "tbank.png",
    "t-bank": "tbank.png",
    "tbank": "tbank.png",
    "вк": "vk.png",
    "vk": "vk.png",
    "ozon": "ozon.png",
    "озон": "ozon.png",
    "wildberries": "wildberries.png",
    "вайлдберриз": "wildberries.png",
    "wb": "wb.png",
    "avito": "avito.png",
    "авито": "avito.png",
    "мтс": "mts.png",
    "mts": "mts.png",
    "мегафон": "megafon.png",
    "megafon": "megafon.png",
    "втб": "vtb.png",
    "vtb": "vtb.png",
    "райффайзен": "raiffeisen.png",
    "raiffeisen": "raiffeisen.png",
    "касперский": "kaspersky.png",
    "kaspersky": "kaspersky.png",
    "контур": "kontur.png",
    "kontur": "kontur.png",
    "x5": "x5.png",
    "2гис": "2gis.png",
    "2gis": "2gis.png",
    "lamoda": "lamoda.png",
    "ламода": "lamoda.png",
    "hh": "hh.png",
    "headhunter": "hh.png",
}

_WORK_FORMAT_LABELS = {
    "remote": "Удалённо",
    "hybrid": "Гибрид",
    "office": "Офис",
    "unknown": "Формат не указан",
}


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def format_salary_line(salary_from: int | None, salary_to: int | None, currency: str | None) -> str:
    rub_from, rub_to, _ = salary_in_rub(salary_from, salary_to, currency)
    if rub_from is None and rub_to is None:
        return "Зарплата не указана"

    def fmt(n: int) -> str:
        return f"{n:,}".replace(",", " ")

    if rub_from is not None and rub_to is not None:
        return f"{fmt(rub_from)} — {fmt(rub_to)} ₽/мес"
    if rub_from is not None:
        return f"от {fmt(rub_from)} ₽/мес"
    return f"до {fmt(rub_to or 0)} ₽/мес"


def work_format_label(work_format: str | None, *, remote: bool = False) -> str:
    if remote and (not work_format or work_format == "unknown"):
        return "Удалённо"
    return _WORK_FORMAT_LABELS.get((work_format or "unknown").lower(), "Формат не указан")


def truncate_text(value: str | None, limit: int) -> str:
    text = re.sub(r"\s+", " ", (value or "").strip())
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)].rstrip() + "…"


def resolve_logo_path(company: str | None) -> Path | None:
    if not company or not _LOGO_DIR.exists():
        return None
    key = company.lower().strip()
    for alias, filename in _COMPANY_LOGO_ALIASES.items():
        if alias in key:
            path = _LOGO_DIR / filename
            if path.exists():
                return path
    return None


def build_caption(
    vacancy: Any,
    *,
    profile_name: str | None = None,
) -> str:
    title = html.escape((vacancy.title or "Вакансия").strip())
    company = html.escape((vacancy.company or "Компания").strip())
    url = html.escape((vacancy.url or "").strip(), quote=True)
    salary = html.escape(format_salary_line(vacancy.salary_from, vacancy.salary_to, vacancy.currency))
    city = html.escape((vacancy.city or "Город не указан").strip())
    fmt = html.escape(work_format_label(vacancy.work_format, remote=bool(vacancy.remote)))
    skills = [str(s).strip() for s in (vacancy.skills or []) if str(s).strip()]
    skills_line = html.escape(", ".join(skills[:12])) if skills else "не указан"
    description = html.escape(truncate_text(vacancy.description, 280) or "Описание не указано")
    source = html.escape(str(vacancy.source or "unknown"))
    profile = html.escape(profile_name or "—")

    link = f'<a href="{url}">{title} @ {company}</a>' if url else f"{title} @ {company}"
    return (
        f"{link}\n"
        f"{salary}\n"
        f"📍 {city}\n"
        f"🏢 {fmt}\n\n"
        f"<b>Стек:</b> {skills_line}\n"
        f"<b>Что делать:</b> {description}\n\n"
        f"Источник: {source} · профиль: {profile}"
    )


def _draw_gradient(img: Image.Image) -> None:
    draw = ImageDraw.Draw(img)
    for y in range(BANNER_H):
        t = y / max(1, BANNER_H - 1)
        r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
        draw.line([(0, y), (BANNER_W, y)], fill=(r, g, b))


def _paste_logo(canvas: Image.Image, company: str | None) -> None:
    box = (48, 48, 48 + 140, 48 + 140)
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    odraw.rounded_rectangle(box, radius=28, fill=LOGO_BG)
    canvas.alpha_composite(overlay)

    logo_path = resolve_logo_path(company)
    if logo_path is not None:
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo.thumbnail((108, 108), Image.Resampling.LANCZOS)
            lx = box[0] + (140 - logo.width) // 2
            ly = box[1] + (140 - logo.height) // 2
            canvas.paste(logo, (lx, ly), logo)
            return
        except OSError:
            pass

    letter = ((company or "?").strip()[:1] or "?").upper()
    draw = ImageDraw.Draw(canvas)
    font = _font(64, bold=True)
    bbox = draw.textbbox((0, 0), letter, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        (box[0] + (140 - tw) // 2, box[1] + (140 - th) // 2 - 4),
        letter,
        font=font,
        fill=TEXT_ACCENT,
    )


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines[:4]


def render_banner_png(vacancy: Any) -> bytes:
    img = Image.new("RGBA", (BANNER_W, BANNER_H), BG_TOP + (255,))
    _draw_gradient(img)
    _paste_logo(img, vacancy.company)

    draw = ImageDraw.Draw(img)
    title_font = _font(54, bold=True)
    salary_font = _font(36, bold=True)
    meta_font = _font(28)

    title = truncate_text(vacancy.title, 90) or "Вакансия"
    text_x = 220
    max_w = BANNER_W - text_x - 48
    lines = _wrap_text(draw, title, title_font, max_w)
    y = 70
    for line in lines:
        draw.text((text_x, y), line, font=title_font, fill=TEXT_DARK)
        y += 62

    salary = format_salary_line(vacancy.salary_from, vacancy.salary_to, vacancy.currency)
    draw.text((text_x, y + 8), salary, font=salary_font, fill=TEXT_ACCENT)

    city = (vacancy.city or "Город не указан").strip()
    fmt = work_format_label(vacancy.work_format, remote=bool(vacancy.remote))
    meta = f"📍  {city}     🏢  {fmt}"
    draw.text((text_x, BANNER_H - 90), meta, font=meta_font, fill=TEXT_SECONDARY)

    buf = BytesIO()
    img.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()
