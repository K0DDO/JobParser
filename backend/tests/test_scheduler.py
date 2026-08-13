from datetime import datetime, timedelta

from app.models import AppSettings
from app.services.settings_service import compute_next_sync, sync_is_due


def test_compute_next_sync_uses_interval():
    settings = AppSettings(sync_interval_minutes=60)
    base = datetime(2026, 8, 12, 12, 0, 0)
    assert compute_next_sync(settings, from_time=base) == base + timedelta(minutes=60)


def test_compute_next_sync_custom_interval():
    settings = AppSettings(sync_interval_minutes=15)
    base = datetime(2026, 8, 12, 12, 0, 0)
    assert compute_next_sync(settings, from_time=base) == base + timedelta(minutes=15)


def test_sync_is_due_when_next_is_in_the_past():
    settings = AppSettings(
        sync_interval_minutes=60,
        sync_in_progress=False,
        next_sync_at=datetime(2026, 8, 13, 2, 39, 0),
    )
    now = datetime(2026, 8, 13, 8, 6, 0)
    assert sync_is_due(settings, now=now) is True


def test_sync_is_due_false_when_in_progress_or_future():
    settings = AppSettings(
        sync_interval_minutes=60,
        sync_in_progress=False,
        next_sync_at=datetime(2026, 8, 13, 9, 0, 0),
    )
    now = datetime(2026, 8, 13, 8, 6, 0)
    assert sync_is_due(settings, now=now) is False
    settings.sync_in_progress = True
    settings.next_sync_at = datetime(2026, 8, 13, 2, 0, 0)
    assert sync_is_due(settings, now=now) is False


def test_sync_is_due_when_next_missing():
    settings = AppSettings(sync_interval_minutes=60, sync_in_progress=False, next_sync_at=None)
    assert sync_is_due(settings, now=datetime(2026, 8, 13, 8, 0, 0)) is True
