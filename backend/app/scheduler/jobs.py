"""APScheduler-based sync and auto-apply worker."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.core.timeutil import utc_now_naive
from app.db.session import AsyncSessionLocal
from app.services.automation import process_pending_queue
from app.services.currency import refresh_rates
from app.services.settings_service import compute_next_sync, get_or_create_settings, sync_is_due
from app.services.sync import clear_stale_sync_lock, run_sync

logger = logging.getLogger(__name__)


def _scheduler_timezone():
    try:
        return ZoneInfo(settings.timezone)
    except (ZoneInfoNotFoundError, Exception):
        logger.warning("Timezone %s unavailable, using UTC", settings.timezone)
        return ZoneInfo("UTC")


scheduler = AsyncIOScheduler(timezone=_scheduler_timezone())
_sync_lock = asyncio.Lock()


async def trigger_manual_sync(*, triggered_by: str = "manual") -> dict:
    """Same entry as the Sync button / POST /sync."""
    if _sync_lock.locked():
        return {"status": "busy", "message": "Sync already in progress"}
    async with _sync_lock:
        return await run_sync(triggered_by=triggered_by)


async def _scheduled_sync_tick() -> None:
    """Every minute: if due, run the exact same path as the Sync button."""
    async with AsyncSessionLocal() as session:
        await clear_stale_sync_lock(session)
        app_settings = await get_or_create_settings(session)
        due = sync_is_due(app_settings)
    if not due:
        return
    logger.info("Scheduled sync: same path as Sync button")
    result = await trigger_manual_sync(triggered_by="manual")
    logger.info("Scheduled sync finished: %s", result.get("status"))


async def _scheduled_queue_worker() -> None:
    async with AsyncSessionLocal() as session:
        app_settings = await get_or_create_settings(session)
        if not app_settings.global_auto_apply:
            return
    await process_pending_queue()


async def _scheduled_fx_refresh() -> None:
    status = await refresh_rates(force=True)
    logger.info("FX refresh: source=%s as_of=%s", status.get("source"), status.get("as_of"))


def start_scheduler() -> None:
    scheduler.add_job(
        _scheduled_sync_tick,
        trigger=IntervalTrigger(minutes=1),
        id="vacancy_sync",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=86_400,
        next_run_time=datetime.now(_scheduler_timezone()),
    )
    scheduler.add_job(
        _scheduled_queue_worker,
        trigger=IntervalTrigger(minutes=1),
        id="auto_apply_worker",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        _scheduled_fx_refresh,
        trigger=IntervalTrigger(hours=6),
        id="fx_rates_refresh",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=86_400,
    )
    if not scheduler.running:
        scheduler.start()
    logger.info("Scheduler started (sync tick every 1 min, catch-up on overdue next_sync_at)")


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


async def reschedule_from_db() -> None:
    """Interval lives in DB next_sync_at; tick job stays at 1 minute."""
    async with AsyncSessionLocal() as session:
        app_settings = await get_or_create_settings(session)
        interval = max(1, int(app_settings.sync_interval_minutes or 60))
        app_settings.sync_interval_minutes = interval
        now = utc_now_naive()
        if app_settings.last_sync_at is None:
            if app_settings.next_sync_at is None:
                app_settings.next_sync_at = now
        else:
            app_settings.next_sync_at = compute_next_sync(app_settings, from_time=app_settings.last_sync_at)
        await session.commit()
        next_at = app_settings.next_sync_at
    logger.info("Sync interval is %s min; next_sync_at=%s", interval, next_at)
