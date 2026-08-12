"""Vacancy sync orchestration: parse → normalize → dedupe → match → queue."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ApplicationStatus, VacancyStatus
from app.core.timeutil import is_stale, utc_now_naive
from app.db.session import AsyncSessionLocal
from app.models import SearchProfile, SourceConfig, Vacancy
from app.parsers import get_source
from app.parsers.base import ParserConfig
from app.services.applications import add_event, create_or_get_application
from app.services.automation import AutoApplyGuard, enqueue_apply, process_pending_queue
from app.services.dedupe import upsert_vacancy
from app.services.filters import vacancy_matches_profile
from app.services.logging_service import add_log, add_notification
from app.services.settings_service import compute_next_sync, get_or_create_settings

logger = logging.getLogger(__name__)

STALE_SYNC_MINUTES = 20


async def clear_stale_sync_lock(session: AsyncSession) -> bool:
    """If sync_in_progress stuck too long, clear it. Returns True if unlocked."""
    settings = await get_or_create_settings(session)
    if not settings.sync_in_progress:
        return False
    marker = settings.updated_at or settings.last_sync_at
    if not is_stale(marker, minutes=STALE_SYNC_MINUTES):
        return False
    settings.sync_in_progress = False
    settings.system_status = "ok"
    await add_log(
        session,
        f"Cleared stale sync lock (older than {STALE_SYNC_MINUTES} min)",
        level="warning",
        category="sync",
    )
    await session.commit()
    return True


async def run_sync(*, triggered_by: str = "scheduler") -> dict:
    async with AsyncSessionLocal() as session:
        await clear_stale_sync_lock(session)
        settings = await get_or_create_settings(session)
        if settings.sync_in_progress:
            return {"status": "busy", "message": "Sync already in progress"}

        settings.sync_in_progress = True
        settings.system_status = "syncing"
        await session.commit()

    stats = {
        "triggered_by": triggered_by,
        "fetched": 0,
        "created": 0,
        "updated": 0,
        "matched": 0,
        "queued": 0,
        "errors": [],
    }
    lock_held = True

    try:
        async with AsyncSessionLocal() as session:
            settings = await get_or_create_settings(session)
            await add_log(session, f"Sync started ({triggered_by})", category="sync")
            await session.commit()

            sources = (
                await session.execute(
                    select(SourceConfig).where(SourceConfig.parsing_enabled.is_(True))
                )
            ).scalars().all()

            profiles = (
                await session.execute(
                    select(SearchProfile).where(SearchProfile.is_active.is_(True))
                )
            ).scalars().all()

            new_vacancies: list[Vacancy] = []

            for source_cfg in sources:
                parser = get_source(source_cfg.name)
                if parser is None:
                    msg = f"{source_cfg.display_name}: parser not registered"
                    stats["errors"].append(msg)
                    await add_log(session, msg, level="error", category="parser")
                    continue

                query_parts: list[str] = []
                for p in profiles:
                    query_parts.extend(p.roles or [])
                    query_parts.extend((p.include_skills or [])[:3])
                query = " OR ".join(dict.fromkeys(query_parts)) if query_parts else None

                config = ParserConfig(
                    query=query,
                    max_pages=10,
                    per_page=50,
                    sources_settings=dict(source_cfg.settings or {}),
                )
                try:
                    vacancies_data = await parser.fetch_vacancies(config)
                except NotImplementedError as exc:
                    source_cfg.status = "unavailable"
                    source_cfg.last_error = str(exc)
                    msg = f"{source_cfg.display_name}: {exc}"
                    stats["errors"].append(msg)
                    await add_log(session, msg, level="warning", category="parser")
                    await session.commit()
                    continue
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Parser %s failed", source_cfg.name)
                    source_cfg.last_error = str(exc)
                    source_cfg.status = "error"
                    msg = f"{source_cfg.display_name} parser failed: {exc}"
                    stats["errors"].append(msg)
                    await add_log(session, msg, level="error", category="parser")
                    await session.commit()
                    continue

                found = 0
                created_count = 0
                for data in vacancies_data:
                    vacancy, created = await upsert_vacancy(session, data)
                    found += 1
                    stats["fetched"] += 1
                    if created:
                        created_count += 1
                        stats["created"] += 1
                        new_vacancies.append(vacancy)
                    else:
                        stats["updated"] += 1

                source_cfg.last_sync_at = utc_now_naive()
                source_cfg.last_error = None
                source_cfg.status = "ready"
                source_cfg.found_today = (source_cfg.found_today or 0) + created_count
                await add_log(
                    session,
                    f"{source_cfg.display_name}: {found} vacancies found ({created_count} new)",
                    category="parser",
                )
                await session.commit()

            all_recent = (
                await session.execute(
                    select(Vacancy).order_by(Vacancy.updated_at.desc()).limit(500)
                )
            ).scalars().all()

            settings = await get_or_create_settings(session)
            guard = AutoApplyGuard(settings)
            source_map = {
                s.name: s
                for s in (await session.execute(select(SourceConfig))).scalars().all()
            }

            for vacancy in all_recent:
                matched_any = False
                for profile in profiles:
                    if not vacancy_matches_profile(vacancy, profile):
                        continue
                    matched_any = True
                    stats["matched"] += 1
                    vacancy.status = VacancyStatus.MATCHED

                    application, created = await create_or_get_application(
                        session,
                        vacancy,
                        profile.id,
                        status=ApplicationStatus.MATCHED,
                    )
                    if created:
                        await add_event(
                            session,
                            application,
                            "matched",
                            f'Vacancy matched profile "{profile.name}"',
                            new_status=ApplicationStatus.MATCHED,
                        )

                    source_cfg = source_map.get(vacancy.source)
                    if source_cfg is None:
                        continue

                    can_queue, reason = await guard.can_enqueue(
                        session, vacancy, profile, source_cfg
                    )
                    if can_queue:
                        item = await enqueue_apply(session, vacancy, profile)
                        if item:
                            stats["queued"] += 1
                            await transition_if_needed(session, application)
                    else:
                        logger.debug("Not enqueueing: %s", reason)

                if matched_any:
                    await session.flush()

            settings.last_sync_at = utc_now_naive()
            settings.next_sync_at = compute_next_sync(settings)
            settings.system_status = "ok"
            await add_log(
                session,
                f"Sync finished: fetched={stats['fetched']} created={stats['created']} "
                f"matched={stats['matched']} queued={stats['queued']}",
                level="success",
                category="sync",
            )
            if stats["created"]:
                await add_notification(
                    session,
                    "Новые вакансии",
                    f"Найдено {stats['created']} новых вакансий",
                )
            await session.commit()

        async with AsyncSessionLocal() as session:
            settings = await get_or_create_settings(session)
            if settings.global_auto_apply:
                processed = await process_pending_queue(session)
                stats["auto_processed"] = processed
            else:
                await add_log(session, "Auto Apply disabled", category="auto_apply")
                await session.commit()
                stats["auto_processed"] = 0

    except Exception as exc:  # noqa: BLE001
        logger.exception("Sync failed")
        async with AsyncSessionLocal() as session:
            settings = await get_or_create_settings(session)
            settings.system_status = "error"
            await add_log(session, f"Sync failed: {exc}", level="error", category="sync")
            await session.commit()
        stats["errors"].append(str(exc))
        stats["status"] = "error"
        return stats
    finally:
        if lock_held:
            try:
                async with AsyncSessionLocal() as session:
                    settings = await get_or_create_settings(session)
                    if settings.sync_in_progress:
                        settings.sync_in_progress = False
                        await session.commit()
            except Exception:  # noqa: BLE001
                logger.exception("Failed to release sync lock")

    stats["status"] = "ok"
    return stats


async def transition_if_needed(session: AsyncSession, application) -> None:
    if application.status == ApplicationStatus.MATCHED:
        application.status = ApplicationStatus.QUEUED
        await add_event(
            session,
            application,
            "queued",
            "Added to auto-apply queue",
            old_status=ApplicationStatus.MATCHED,
            new_status=ApplicationStatus.QUEUED,
        )
