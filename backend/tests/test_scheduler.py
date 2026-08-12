from datetime import datetime, timedelta

from app.models import AppSettings
from app.services.settings_service import compute_next_sync


def test_compute_next_sync_uses_interval():
    settings = AppSettings(sync_interval_minutes=60)
    base = datetime(2026, 8, 12, 12, 0, 0)
    assert compute_next_sync(settings, from_time=base) == base + timedelta(minutes=60)


def test_compute_next_sync_custom_interval():
    settings = AppSettings(sync_interval_minutes=15)
    base = datetime(2026, 8, 12, 12, 0, 0)
    assert compute_next_sync(settings, from_time=base) == base + timedelta(minutes=15)
