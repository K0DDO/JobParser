"""Tests for sync lookback window filtering."""

from datetime import datetime, timedelta

from app.core.enums import ExperienceLevel, SourceName, WorkFormat
from app.schemas import VacancyData
from app.services.sync import filter_by_lookback, within_lookback


def _item(vid: str, published: datetime | None) -> VacancyData:
    return VacancyData(
        source=SourceName.HH,
        source_vacancy_id=vid,
        url=f"https://hh.ru/vacancy/{vid}",
        title=f"Job {vid}",
        work_format=WorkFormat.REMOTE,
        experience=ExperienceLevel.UNKNOWN,
        published_at=published,
    )


def test_within_lookback_window():
    now = datetime(2026, 8, 24, 12, 0, 0)
    assert within_lookback(now - timedelta(days=3), 7, now=now) is True
    assert within_lookback(now - timedelta(days=10), 7, now=now) is False
    assert within_lookback(None, 7, now=now) is True
    assert within_lookback(now - timedelta(days=100), None, now=now) is True


def test_filter_by_lookback_keeps_recent_and_unknown():
    now = datetime(2026, 8, 24, 12, 0, 0)
    items = [
        _item("1", now - timedelta(days=2)),
        _item("2", now - timedelta(days=20)),
        _item("3", None),
    ]
    kept = filter_by_lookback(items, 7, now=now)
    assert [i.source_vacancy_id for i in kept] == ["1", "3"]
