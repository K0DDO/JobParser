"""APScheduler-based sync and auto-apply worker."""

from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.services.automation import process_pending_queue
from app.services.currency import refresh_rates
from app.services.settings_service import get_or_create_settings
from app.services.sync import run_sync

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone=settings.timezone)
_sync_lock = asyncio.Lock()


async def _scheduled_sync() -> None:
    if _sync_lock.locked():
        logger.info("Skipping scheduled sync — already running")
        return
    async with _sync_lock:
        logger.info("Scheduled sync starting")
        result = await run_sync(triggered_by="scheduler")
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


async def trigger_manual_sync() -> dict:
    if _sync_lock.locked():
        return {"status": "busy", "message": "Sync already in progress"}
    async with _sync_lock:
        return await run_sync(triggered_by="manual")


def start_scheduler() -> None:
    interval = settings.sync_interval_minutes
    scheduler.add_job(
        _scheduled_sync,
        trigger=IntervalTrigger(minutes=interval),
        id="vacancy_sync",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        _scheduled_queue_worker,
        trigger=IntervalTrigger(minutes=1),
        id="auto_apply_worker",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        _scheduled_fx_refresh,
        trigger=IntervalTrigger(hours=6),
        id="fx_rates_refresh",
        replace_existing=True,
        max_instances=1,
    )
    if not scheduler.running:
        scheduler.start()
    logger.info("Scheduler started (sync every %s min, FX every 6h)", interval)


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


async def reschedule_from_db() -> None:
    async with AsyncSessionLocal() as session:
        app_settings = await get_or_create_settings(session)
        interval = app_settings.sync_interval_minutes
    scheduler.reschedule_job("vacancy_sync", trigger=IntervalTrigger(minutes=interval))
    logger.info("Sync interval updated to %s minutes", interval)
