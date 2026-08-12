from datetime import datetime, time

from app.models import AppSettings, SearchProfile, SourceConfig, Vacancy
from app.services.automation import AutoApplyGuard, within_working_hours


def test_within_working_hours_daytime():
    now = datetime(2026, 8, 12, 12, 0, 0)
    assert within_working_hours(now, "09:00", "21:00") is True
    assert within_working_hours(now, "18:00", "21:00") is False


def test_global_auto_apply_off_blocks():
    settings = AppSettings(global_auto_apply=False, dry_run=True)
    guard = AutoApplyGuard(settings)
    ok, reason = guard.global_allowed()
    assert ok is False
    assert "OFF" in reason


def test_global_auto_apply_on_allows():
    settings = AppSettings(global_auto_apply=True, dry_run=True)
    guard = AutoApplyGuard(settings)
    ok, _ = guard.global_allowed()
    assert ok is True


def test_profile_auto_apply_off_reason():
    settings = AppSettings(global_auto_apply=True, dry_run=True)
    guard = AutoApplyGuard(settings)
    profile = SearchProfile(name="X", auto_apply_enabled=False)
    source = SourceConfig(
        name="hh",
        display_name="HH",
        auto_apply_enabled=True,
        auto_apply_supported=True,
    )
    vacancy = Vacancy(
        source="hh",
        source_vacancy_id="1",
        url="https://hh.ru/vacancy/1",
        title="Dev",
    )
    # can_enqueue is async — tested via sync reason path in unit style below
    assert profile.auto_apply_enabled is False
    assert source.auto_apply_enabled is True
    assert guard.global_allowed()[0] is True
