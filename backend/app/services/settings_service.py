from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutil import utc_now_naive
from app.core.config import settings as env_settings
from app.core.enums import SourceName
from app.models import AppSettings, SourceConfig
from app.parsers import get_all_sources


DEFAULT_SOURCES = [
    (SourceName.HH, "HH", False, True, "error"),
    (SourceName.HABR, "Habr Career", True, False, "ready"),
    (SourceName.HIRIFY, "Hirify", True, False, "ready"),
    (SourceName.TALANTO, "Talanto", True, False, "ready"),
    (SourceName.GETMATCH, "GetMatch", True, False, "ready"),
    (SourceName.REMOTEOK, "Remote OK", True, False, "ready"),
    (SourceName.REMOTIVE, "Remotive", True, False, "ready"),
    (SourceName.HIMALAYAS, "Himalayas", True, False, "ready"),
    (SourceName.JOBICY, "Jobicy", True, False, "ready"),
    (SourceName.ARBEITNOW, "Arbeitnow", True, False, "ready"),
    (SourceName.WEWORKREMOTELY, "We Work Remotely", True, False, "ready"),
    (SourceName.WORKINGNOMADS, "Working Nomads", True, False, "ready"),
    (SourceName.GREENHOUSE, "Company Careers", True, False, "ready"),
]


async def get_or_create_settings(session: AsyncSession) -> AppSettings:
    result = await session.execute(select(AppSettings).limit(1))
    row = result.scalar_one_or_none()
    if row:
        if not row.timezone:
            row.timezone = "Europe/Moscow"
        return row
    row = AppSettings(
        sync_interval_minutes=env_settings.sync_interval_minutes,
        timezone=env_settings.timezone or "Europe/Moscow",
        global_auto_apply=False,
        dry_run=True,
    )
    session.add(row)
    await session.flush()
    return row


async def ensure_default_sources(session: AsyncSession) -> list[SourceConfig]:
    result = await session.execute(select(SourceConfig))
    existing = {s.name: s for s in result.scalars().all()}
    sources_meta = {s.name: s for s in get_all_sources().values()}

    created: list[SourceConfig] = []
    for name, display, parsing, auto_apply, status in DEFAULT_SOURCES:
        if name in existing:
            src = existing[name]
            meta = sources_meta.get(name)
            if meta:
                src.auto_apply_supported = meta.auto_apply_supported
                src.display_name = meta.display_name
            if name in {SourceName.HIRIFY, SourceName.TALANTO, SourceName.GETMATCH} and src.status == "unavailable":
                src.parsing_enabled = True
                src.status = "ready"
                src.last_error = None
            if name == SourceName.HABR and src.status == "unavailable":
                src.parsing_enabled = True
                src.status = "ready"
                src.last_error = None
                hh = existing.get(SourceName.HH)
                if hh is not None:
                    hh.parsing_enabled = False
                    hh.status = "error"
                    hh.last_error = (
                        "HH parsing paused: application is not approved and API returns 403. "
                        "Vacancies are collected from Habr Career. Enable HH later in Sources."
                    )
            continue
        meta = sources_meta.get(name)
        src = SourceConfig(
            name=name,
            display_name=display,
            parsing_enabled=parsing,
            auto_apply_enabled=False,
            auto_apply_supported=meta.auto_apply_supported if meta else auto_apply,
            status=status,
        )
        session.add(src)
        created.append(src)

    await session.flush()
    result = await session.execute(select(SourceConfig).order_by(SourceConfig.id))
    return list(result.scalars().all())


def compute_next_sync(settings_row: AppSettings, from_time: datetime | None = None) -> datetime:
    base = from_time or utc_now_naive()
    minutes = max(1, int(settings_row.sync_interval_minutes or 60))
    return base + timedelta(minutes=minutes)


def sync_is_due(settings_row: AppSettings, now: datetime | None = None) -> bool:
    """True when a scheduled sync should run (including catch-up after sleep/restart)."""
    if settings_row.sync_in_progress:
        return False
    current = now or utc_now_naive()
    if settings_row.next_sync_at is None:
        return True
    return settings_row.next_sync_at <= current
