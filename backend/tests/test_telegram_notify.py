"""Tests for Telegram notify gating (no network)."""

import pytest
from types import SimpleNamespace

from app.services import telegram as telegram_mod


@pytest.mark.asyncio
async def test_send_vacancy_card_skips_already_notified(monkeypatch):
    vacancy = SimpleNamespace(
        id=1,
        title="Dev",
        company="Acme",
        url="https://example.com/1",
        salary_from=100,
        salary_to=200,
        currency="RUB",
        city="Москва",
        remote=True,
        work_format="remote",
        skills=["Python"],
        description="Build APIs",
        source="hh",
        telegram_notified_at="already",
    )
    monkeypatch.setattr(telegram_mod, "telegram_configured", lambda: True)

    async def boom(*_a, **_k):
        raise AssertionError("should not send")

    monkeypatch.setattr(telegram_mod, "send_photo_bytes", boom)
    assert await telegram_mod.send_vacancy_card(vacancy, profile_name="P") is False


@pytest.mark.asyncio
async def test_notify_marks_sent(monkeypatch):
    vacancy = SimpleNamespace(
        id=7,
        title="Dev",
        company="Acme",
        url="https://example.com/7",
        salary_from=100_000,
        salary_to=200_000,
        currency="RUB",
        city="Москва",
        remote=True,
        work_format="remote",
        skills=["Python"],
        description="Build APIs",
        source="hh",
        telegram_notified_at=None,
    )

    class FakeSession:
        async def flush(self):
            return None

    monkeypatch.setattr(telegram_mod, "telegram_configured", lambda: True)

    async def fake_send(*_a, **_k):
        return {"ok": True}

    monkeypatch.setattr(telegram_mod, "send_photo_bytes", fake_send)
    monkeypatch.setattr(telegram_mod, "SEND_GAP_SECONDS", 0)

    sent = await telegram_mod.notify_new_matched_vacancies(
        FakeSession(),
        [(vacancy, "Backend")],
    )
    assert sent == 1
    assert vacancy.telegram_notified_at is not None


@pytest.mark.asyncio
async def test_notify_skips_when_disabled(monkeypatch):
    monkeypatch.setattr(telegram_mod, "telegram_configured", lambda: False)
    vacancy = SimpleNamespace(id=1, telegram_notified_at=None)

    class FakeSession:
        async def flush(self):
            return None

    sent = await telegram_mod.notify_new_matched_vacancies(
        FakeSession(),
        [(vacancy, "P")],
    )
    assert sent == 0
