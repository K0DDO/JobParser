"""Tests for Telegram vacancy card caption and banner."""

from types import SimpleNamespace

from app.services.telegram_cards import (
    build_caption,
    format_salary_line,
    render_banner_png,
    truncate_text,
    work_format_label,
)
from app.services.telegram import telegram_configured


def _vacancy(**kwargs):
    base = dict(
        id=1,
        title="Team lead data science",
        company="Альфа-Банк",
        url="https://hh.ru/vacancy/1",
        salary_from=450_000,
        salary_to=500_000,
        currency="RUB",
        city="Москва",
        remote=False,
        work_format="hybrid",
        skills=["Python", "Pandas", "Spark"],
        description="Manage ML model development and reviews.",
        source="hh",
        telegram_notified_at=None,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_format_salary_line_range():
    assert format_salary_line(450_000, 500_000, "RUB") == "450 000 — 500 000 ₽/мес"


def test_work_format_label():
    assert work_format_label("hybrid") == "Гибрид"
    assert work_format_label("unknown", remote=True) == "Удалённо"


def test_truncate_text():
    assert truncate_text("a" * 10, 8).endswith("…")
    assert len(truncate_text("a" * 10, 8)) == 8


def test_build_caption_html():
    caption = build_caption(_vacancy(), profile_name="Backend")
    assert '<a href="https://hh.ru/vacancy/1">Team lead data science @ Альфа-Банк</a>' in caption
    assert "450 000 — 500 000 ₽/мес" in caption
    assert "📍 Москва" in caption
    assert "🏢 Гибрид" in caption
    assert "<b>Стек:</b> Python, Pandas, Spark" in caption
    assert "<b>Что делать:</b> Manage ML model development and reviews." in caption
    assert "профиль: Backend" in caption


def test_build_caption_escapes_html():
    caption = build_caption(
        _vacancy(title='A <b>x</b>', company='C&D', description='1 < 2'),
        profile_name="P",
    )
    assert "<b>x</b>" not in caption or "&lt;b&gt;" in caption
    assert "&amp;" in caption or "C&amp;D" in caption


def test_render_banner_png_nonempty():
    png = render_banner_png(_vacancy())
    assert isinstance(png, bytes)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 5_000


def test_telegram_configured_false_without_env(monkeypatch):
    from app.core import config as config_mod

    monkeypatch.setattr(config_mod.settings, "telegram_enabled", True)
    monkeypatch.setattr(config_mod.settings, "telegram_bot_token", "")
    monkeypatch.setattr(config_mod.settings, "telegram_chat_id", "")
    assert telegram_configured() is False
