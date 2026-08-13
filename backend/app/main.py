from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.core.logging import setup_logging
from app.db.session import AsyncSessionLocal
from app.scheduler.jobs import reschedule_from_db, start_scheduler, stop_scheduler
from app.services.currency import refresh_rates
from app.core.timeutil import utc_now_naive
from app.services.salary_backfill import backfill_monthly_salaries
from app.services.settings_service import ensure_default_sources, get_or_create_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    async with AsyncSessionLocal() as session:
        settings = await get_or_create_settings(session)
        await ensure_default_sources(session)
        if settings.sync_in_progress:
            settings.sync_in_progress = False
            settings.system_status = "ok"
        if settings.next_sync_at is None:
            settings.next_sync_at = utc_now_naive()
        await session.commit()
        try:
            n = await backfill_monthly_salaries(session)
            if n:
                logger.info("Startup salary backfill updated %s vacancies", n)
        except Exception:  # noqa: BLE001
            logger.exception("Salary backfill failed")
    await refresh_rates(force=True)
    start_scheduler()
    await reschedule_from_db()
    yield
    stop_scheduler()


app = FastAPI(
    title="JobParser API",
    description="Local automated job search application",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/")
async def root() -> dict:
    return {"app": "JobParser", "docs": "/docs", "health": "/api/v1/health"}
