"""Critical safety tests for auto-apply behavior."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.enums import ApplicationStatus, QueueItemStatus
from app.models import Application, ApplyQueueItem, AppSettings, SearchProfile, Vacancy
from app.services.automation import AutoApplyGuard, process_queue_item


@pytest.mark.asyncio
async def test_process_queue_skips_when_global_off():
    settings = AppSettings(id=1, global_auto_apply=False, dry_run=False, global_daily_limit=50)
    vacancy = Vacancy(
        id=1,
        source="hh",
        source_vacancy_id="1",
        url="https://hh.ru/vacancy/1",
        title="Python Dev",
        company="Acme",
    )
    profile = SearchProfile(id=1, name="P", auto_apply_enabled=True, daily_apply_limit=30)
    item = ApplyQueueItem(
        id=1,
        vacancy_id=1,
        profile_id=1,
        status=QueueItemStatus.PENDING,
        attempts=0,
        max_attempts=3,
        scheduled_at=datetime.utcnow(),
    )

    session = AsyncMock()
    session.get = AsyncMock(side_effect=[vacancy, profile])
    session.flush = AsyncMock()

    with patch("app.services.automation.add_log", new_callable=AsyncMock):
        await process_queue_item(session, item, settings)

    assert item.status == QueueItemStatus.SKIPPED
    assert "Global Auto Apply is OFF" in (item.last_error or "")


@pytest.mark.asyncio
async def test_dry_run_does_not_call_source_apply():
    settings = AppSettings(id=1, global_auto_apply=True, dry_run=True, global_daily_limit=50)
    vacancy = Vacancy(
        id=1,
        source="hh",
        source_vacancy_id="1",
        url="https://hh.ru/vacancy/1",
        title="Python Dev",
        company="Acme",
    )
    profile = SearchProfile(
        id=1,
        name="P",
        auto_apply_enabled=True,
        daily_apply_limit=30,
        no_reapply=True,
    )
    item = ApplyQueueItem(
        id=1,
        vacancy_id=1,
        profile_id=1,
        status=QueueItemStatus.PENDING,
        attempts=0,
        max_attempts=3,
        scheduled_at=datetime.utcnow(),
    )

    session = AsyncMock()
    session.get = AsyncMock(side_effect=[vacancy, profile])
    session.flush = AsyncMock()
    session.add = MagicMock()

    fake_app = Application(
        id=1,
        vacancy_id=1,
        profile_id=1,
        status=ApplicationStatus.QUEUED,
        is_auto=True,
        is_dry_run=True,
    )

    with (
        patch("app.services.automation.add_log", new_callable=AsyncMock),
        patch(
            "app.services.automation.create_or_get_application",
            new_callable=AsyncMock,
            return_value=(fake_app, True),
        ),
        patch(
            "app.services.automation.transition_status",
            new_callable=AsyncMock,
            return_value=fake_app,
        ),
        patch(
            "app.services.automation.count_applies_today",
            new_callable=AsyncMock,
            return_value=0,
        ),
        patch(
            "app.services.automation.has_any_application",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch("app.services.automation.get_source") as get_source,
    ):
        await process_queue_item(session, item, settings)
        get_source.assert_not_called()

    assert item.status == QueueItemStatus.DRY_RUN


@pytest.mark.asyncio
async def test_daily_limit_blocks_send():
    settings = AppSettings(id=1, global_auto_apply=True, dry_run=False, global_daily_limit=30)
    guard = AutoApplyGuard(settings)
    vacancy = Vacancy(
        id=1,
        source="hh",
        source_vacancy_id="1",
        url="https://hh.ru/vacancy/1",
        title="Dev",
        company="Acme",
    )
    profile = SearchProfile(id=1, name="P", auto_apply_enabled=True, daily_apply_limit=30)

    session = AsyncMock()
    with patch(
        "app.services.automation.count_applies_today",
        new_callable=AsyncMock,
        return_value=30,
    ):
        ok, reason = await guard.can_send(session, vacancy, profile)
    assert ok is False
    assert "limit" in reason.lower()


@pytest.mark.asyncio
async def test_emergency_stop_disables_global():
    from app.services.automation import emergency_stop

    settings = AppSettings(id=1, global_auto_apply=True, dry_run=False)
    pending = ApplyQueueItem(
        id=1,
        vacancy_id=1,
        profile_id=1,
        status=QueueItemStatus.PENDING,
        scheduled_at=datetime.utcnow(),
    )

    session = AsyncMock()
    result_settings = MagicMock()
    result_settings.scalar_one.return_value = settings
    result_pending = MagicMock()
    result_pending.scalars.return_value.all.return_value = [pending]
    session.execute = AsyncMock(side_effect=[result_settings, result_pending])
    session.commit = AsyncMock()

    with patch("app.services.automation.add_log", new_callable=AsyncMock):
        out = await emergency_stop(session)

    assert out.global_auto_apply is False
    assert pending.status == QueueItemStatus.SKIPPED
    assert pending.last_error == "Emergency stop"
