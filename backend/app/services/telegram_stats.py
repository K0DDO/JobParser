"""Vacancy statistics for Telegram: by source + matched by filters."""

from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Vacancy
from app.services.telegram_filters import (
    TELEGRAM_PORTALS,
    load_filters_from_settings,
    vacancy_matches_telegram_filters,
)

PORTAL_LABELS = {key: label for key, label in TELEGRAM_PORTALS}


def _label(source: str) -> str:
    return PORTAL_LABELS.get(source, source)


async def collect_vacancy_stats(
    session: AsyncSession,
    *,
    filters: dict[str, Any] | None = None,
    match_sample_limit: int = 4000,
) -> dict[str, Any]:
    """Counts active/removed by source + how many match telegram filters per source."""
    if filters is None:
        from app.services.settings_service import get_or_create_settings

        settings = await get_or_create_settings(session)
        filters = load_filters_from_settings(settings)

    active_rows = (
        await session.execute(
            select(Vacancy.source, func.count(Vacancy.id))
            .where(Vacancy.removed_at.is_(None))
            .group_by(Vacancy.source)
            .order_by(func.count(Vacancy.id).desc())
        )
    ).all()
    removed_rows = (
        await session.execute(
            select(Vacancy.source, func.count(Vacancy.id))
            .where(Vacancy.removed_at.is_not(None))
            .group_by(Vacancy.source)
            .order_by(func.count(Vacancy.id).desc())
        )
    ).all()
    total_active = sum(int(c) for _, c in active_rows)
    total_removed = sum(int(c) for _, c in removed_rows)

    # Matched-by-filters: sample recent active vacancies (full scan can be heavy)
    result = await session.execute(
        select(Vacancy)
        .where(Vacancy.removed_at.is_(None))
        .order_by(Vacancy.updated_at.desc())
        .limit(match_sample_limit)
    )
    vacancies = list(result.scalars().all())
    matched_by_source: Counter[str] = Counter()
    matched_total = 0
    for vac in vacancies:
        if vacancy_matches_telegram_filters(vac, filters):
            matched_total += 1
            matched_by_source[vac.source or "?"] += 1

    return {
        "total_active": total_active,
        "total_removed": total_removed,
        "by_source_active": [(str(s), int(c)) for s, c in active_rows],
        "by_source_removed": [(str(s), int(c)) for s, c in removed_rows],
        "matched_total": matched_total,
        "matched_scanned": len(vacancies),
        "matched_by_source": matched_by_source.most_common(),
        "filters": filters,
    }


def format_stats_message(stats: dict[str, Any]) -> str:
    lines = [
        "<b>Статистика вакансий</b>",
        f"Активных: <b>{stats['total_active']}</b> · "
        f"удалённых (история): <b>{stats['total_removed']}</b>",
        "",
        "<b>По сайтам (активные)</b>",
    ]
    if stats["by_source_active"]:
        for source, count in stats["by_source_active"]:
            lines.append(f"· {_label(source)}: <b>{count}</b>")
    else:
        lines.append("· пусто")

    if stats["by_source_removed"]:
        lines.append("")
        lines.append("<b>Удалённые по сайтам</b>")
        for source, count in stats["by_source_removed"]:
            lines.append(f"· {_label(source)}: <b>{count}</b>")

    lines.append("")
    lines.append(
        f"<b>Подходят под фильтры</b> "
        f"(из последних {stats['matched_scanned']}): <b>{stats['matched_total']}</b>"
    )
    if stats["matched_by_source"]:
        for source, count in stats["matched_by_source"]:
            lines.append(f"· {_label(source)}: <b>{count}</b>")
    else:
        lines.append("· нет совпадений (или фильтры пустые)")

    lines.append("")
    lines.append("Удалённые не стираются — остаются в истории с меткой removed.")
    return "\n".join(lines)
