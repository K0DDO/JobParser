"""Vacancy sync orchestration: parse → normalize → dedupe → match → queue."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ApplicationStatus, SourceName, VacancyStatus
from app.core.timeutil import is_stale, utc_now_naive
from app.db.session import AsyncSessionLocal
from app.models import SearchProfile, SourceConfig, Vacancy
from app.parsers import get_source
from app.parsers.base import ParserConfig
from app.schemas import VacancyData
from app.services.applications import add_event, create_or_get_application
from app.services.automation import AutoApplyGuard, enqueue_apply, process_pending_queue
from app.services.dedupe import upsert_vacancy
from app.services.filters import vacancy_matches_profile
from app.services.hh_auth import ensure_hh_token
from app.services.logging_service import add_log, add_notification
from app.services.settings_service import compute_next_sync, get_or_create_settings
from app.services.telegram import notify_new_matched_vacancies, telegram_configured
from app.services.telegram_filters import vacancy_matches_telegram_filters

logger = logging.getLogger(__name__)

STALE_SYNC_MINUTES = 8


def sync_max_pages(lookback_days: int) -> int:
    """Fetch deeper history when the lookback window is wider."""
    if lookback_days <= 1:
        return 5
    if lookback_days <= 7:
        return 10
    if lookback_days <= 14:
        return 15
    return 20


def within_lookback(
    published_at: datetime | None,
    lookback_days: int | None,
    *,
    now: datetime | None = None,
) -> bool:
    """True if vacancy is within lookback window (or date unknown / no limit)."""
    if lookback_days is None or lookback_days <= 0:
        return True
    if published_at is None:
        return True
    cutoff = (now or utc_now_naive()) - timedelta(days=lookback_days)
    return published_at >= cutoff


def filter_by_lookback(
    items: list[VacancyData],
    lookback_days: int | None,
    *,
    now: datetime | None = None,
) -> list[VacancyData]:
    if lookback_days is None or lookback_days <= 0:
        return items
    stamp = now or utc_now_naive()
    return [item for item in items if within_lookback(item.published_at, lookback_days, now=stamp)]


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
            lookback_days = max(1, min(90, int(settings.sync_lookback_days or 7)))
            max_pages = sync_max_pages(lookback_days)
            await add_log(
                session,
                f"Sync lookback: last {lookback_days} day(s), max_pages={max_pages}",
                category="sync",
            )
            await session.commit()

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

                source_settings = dict(source_cfg.settings or {})
                if source_cfg.name == SourceName.HH:
                    hh_token = await ensure_hh_token(session)
                    if hh_token:
                        source_settings["access_token"] = hh_token
                        await session.commit()
                    else:
                        await add_log(
                            session,
                            "HH: нет access token — будет попытка API без Bearer, затем RSS",
                            level="warning",
                            category="parser",
                        )
                        await session.commit()

                config = ParserConfig(
                    query=query,
                    max_pages=max_pages,
                    per_page=50,
                    sources_settings=source_settings,
                    lookback_days=lookback_days,
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

                vacancies_data = filter_by_lookback(vacancies_data, lookback_days)

                found = 0
                created_count = 0
                updated_count = 0
                for data in vacancies_data:
                    try:
                        async with session.begin_nested():
                            vacancy, created = await upsert_vacancy(session, data)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Skip vacancy %s/%s: %s", data.source, data.source_vacancy_id, exc)
                        stats["errors"].append(f"{source_cfg.display_name}: skip {data.title[:80]} ({exc})")
                        continue
                    found += 1
                    stats["fetched"] += 1
                    if created:
                        created_count += 1
                        stats["created"] += 1
                        new_vacancies.append(vacancy)
                    else:
                        updated_count += 1
                        stats["updated"] += 1

                source_cfg.last_sync_at = utc_now_naive()
                source_cfg.last_error = None
                source_cfg.status = "ready"
                source_cfg.found_today = (source_cfg.found_today or 0) + created_count
                await add_log(
                    session,
                    f"{source_cfg.display_name}: {found} vacancies ({created_count} new, {updated_count} updated)",
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
            new_ids = {v.id for v in new_vacancies if v.id is not None}
            telegram_queue: list[tuple[Vacancy, str | None]] = []
            telegram_queued_ids: set[int] = set()

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

                    if (
                        vacancy.id in new_ids
                        and vacancy.id not in telegram_queued_ids
                        and vacancy.telegram_notified_at is None
                        and vacancy_matches_telegram_filters(
                            vacancy,
                            roles=settings.telegram_roles,
                            work_formats=settings.telegram_work_formats,
                        )
                    ):
                        telegram_queue.append((vacancy, profile.name))
                        telegram_queued_ids.add(vacancy.id)

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

            tg_sent = 0
            if (
                settings.notifications_enabled
                and telegram_configured()
                and telegram_queue
            ):
                tg_sent = await notify_new_matched_vacancies(session, telegram_queue)
                stats["telegram_sent"] = tg_sent
                if tg_sent:
                    await add_log(
                        session,
                        f"Telegram: sent {tg_sent} vacancy card(s)",
                        level="success",
                        category="telegram",
                    )

            settings.last_sync_at = utc_now_naive()
            settings.next_sync_at = compute_next_sync(settings)
            settings.system_status = "ok"
            await add_log(
                session,
                f"Sync finished (lookback={lookback_days}d): fetched={stats['fetched']} "
                f"created={stats['created']} updated={stats['updated']} "
                f"matched={stats['matched']} queued={stats['queued']}"
                + (f" telegram={tg_sent}" if tg_sent else ""),
                level="success",
                category="sync",
            )
            if stats["created"]:
                await add_notification(
                    session,
                    "Новые вакансии",
                    f"Найдено {stats['created']} новых вакансий",
                )
            elif stats["fetched"]:
                await add_notification(
                    session,
                    "Синхронизация завершена",
                    f"Обработано {stats['fetched']} вакансий за {lookback_days} дн. "
                    f"(новых: {stats['created']}, уже в базе: {stats['updated']})",
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
            settings.last_sync_at = utc_now_naive()
            settings.next_sync_at = compute_next_sync(settings)
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
