"""Timezone helpers. DB keeps naive UTC; API/UI show Europe/Moscow."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

MSK = ZoneInfo("Europe/Moscow")
UTC = timezone.utc


def utc_now_naive() -> datetime:
    """UTC now without tzinfo — matches existing DB columns."""
    return datetime.now(UTC).replace(tzinfo=None)


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def to_msk(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return ensure_utc(dt).astimezone(MSK)


def msk_isoformat(dt: datetime | None) -> str | None:
    """Serialize datetime as Moscow local ISO with offset, e.g. 2026-08-12T18:30:00+03:00."""
    msk = to_msk(dt)
    if msk is None:
        return None
    return msk.isoformat(timespec="seconds")


def msk_today_start_utc_naive() -> datetime:
    """Start of current Moscow calendar day, as naive UTC for DB comparisons."""
    now_msk = datetime.now(MSK)
    start_msk = now_msk.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_msk.astimezone(UTC).replace(tzinfo=None)


def is_stale(since: datetime | None, *, minutes: int = 20) -> bool:
    if since is None:
        return True
    return utc_now_naive() - since.replace(tzinfo=None) > timedelta(minutes=minutes)
