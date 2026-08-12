from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.core.logging import setup_logging
from app.db.session import AsyncSessionLocal
from app.scheduler.jobs import start_scheduler, stop_scheduler
from app.services.currency import refresh_rates
from app.services.settings_service import ensure_default_sources, get_or_create_settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    async with AsyncSessionLocal() as session:
        await get_or_create_settings(session)
        await ensure_default_sources(session)
        await session.commit()
    await refresh_rates(force=True)
    start_scheduler()
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
