"""Recompute stored salaries to monthly using original source amounts."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Vacancy
from app.schemas import VacancyData
from app.services.normalize import detect_salary_period, normalize_vacancy

logger = logging.getLogger(__name__)


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    return None if number == 0 else number


def original_salary_fields(vacancy: Vacancy) -> tuple[int | None, int | None, str | None, str | None]:
    """Return (from, to, currency, period) from raw_data when possible."""
    raw = vacancy.raw_data or {}
    source = vacancy.source
    fallback_cur = vacancy.currency

    if source == "himalayas":
        return (
            _as_int(raw.get("minSalary")),
            _as_int(raw.get("maxSalary")),
            raw.get("currency") or fallback_cur,
            str(raw.get("salaryPeriod") or "annual"),
        )
    if source == "workingnomads":
        text = str(raw.get("salary_range") or raw.get("salary_range_short") or "").strip()
        if text:
            from app.parsers.workingnomads import _parse_salary_text

            salary_from, salary_to, currency = _parse_salary_text(text)
            period = detect_salary_period(text, salary_from or salary_to, currency or "USD", salary_text=text)
            return salary_from, salary_to, currency or fallback_cur or "USD", period
        annual = _as_int(raw.get("annual_salary_usd"))
        if annual:
            return annual, None, "USD", "yearly"
        return vacancy.salary_from, vacancy.salary_to, fallback_cur, None
    if source == "remoteok":
        return (
            _as_int(raw.get("salary_min")),
            _as_int(raw.get("salary_max")),
            "USD",
            "yearly",
        )
    if source == "remotive":
        from app.parsers.remotive import _parse_salary

        salary_from, salary_to, currency = _parse_salary(raw.get("salary"))
        period = detect_salary_period(
            str(raw.get("salary") or ""),
            salary_from or salary_to,
            currency,
            salary_text=str(raw.get("salary") or ""),
        )
        return salary_from, salary_to, currency or fallback_cur, period
    if source == "talanto":
        return (
            _as_int(raw.get("salary_min")),
            _as_int(raw.get("salary_max")),
            raw.get("salary_currency") or fallback_cur,
            None,
        )
    if source == "hirify":
        salary = raw.get("salary") or {}
        if isinstance(salary, dict):
            return (
                _as_int(salary.get("from")),
                _as_int(salary.get("to")),
                salary.get("currency") or fallback_cur,
                "monthly",
            )
    if source == "getmatch":
        salary_from = _as_int(raw.get("salary_display_from"))
        salary_to = _as_int(raw.get("salary_display_to"))
        currency = raw.get("salary_currency") or fallback_cur
        if salary_from is None and salary_to is None:
            base = raw.get("baseSalary") or {}
            value = base.get("value") if isinstance(base, dict) else {}
            if isinstance(value, dict):
                salary_from = _as_int(value.get("minValue"))
                salary_to = _as_int(value.get("maxValue"))
                currency = base.get("currency") or currency
        return salary_from, salary_to, currency, "monthly"
    if source in {"habr", "hh"}:
        salary = raw.get("salary") or {}
        if isinstance(salary, dict):
            return (
                _as_int(salary.get("from")),
                _as_int(salary.get("to")),
                salary.get("currency") or fallback_cur,
                "monthly",
            )
    return vacancy.salary_from, vacancy.salary_to, fallback_cur, None


async def backfill_monthly_salaries(session: AsyncSession) -> int:
    rows = (
        (
            await session.execute(
                select(Vacancy).where(
                    or_(
                        Vacancy.salary_from.is_not(None),
                        Vacancy.salary_to.is_not(None),
                        Vacancy.raw_data.is_not(None),
                    )
                )
            )
        )
        .scalars()
        .all()
    )
    updated = 0
    for vacancy in rows:
        try:
            salary_from, salary_to, currency, period = original_salary_fields(vacancy)
        except Exception:  # noqa: BLE001
            logger.warning("Skip salary backfill for %s/%s", vacancy.source, vacancy.source_vacancy_id)
            continue
        if isinstance(period, (list, tuple)):
            period = next((x for x in period if x), None)
        if salary_from is None and salary_to is None:
            if vacancy.salary_from == 0 or vacancy.salary_to == 0:
                vacancy.salary_from = None if vacancy.salary_from == 0 else vacancy.salary_from
                vacancy.salary_to = None if vacancy.salary_to == 0 else vacancy.salary_to
                if vacancy.salary_from is None and vacancy.salary_to is None:
                    vacancy.currency = None
                updated += 1
            continue
        try:
            data = VacancyData(
                source=vacancy.source,
                source_vacancy_id=vacancy.source_vacancy_id,
                url=vacancy.url or "https://example.invalid/vacancy",
                title=vacancy.title or "Untitled",
                company=vacancy.company,
                description=vacancy.description,
                salary_from=salary_from,
                salary_to=salary_to,
                currency=currency,
                salary_period=str(period) if period else None,
                city=vacancy.city,
                remote=bool(vacancy.remote),
                work_format=vacancy.work_format or "unknown",
                employment_type=vacancy.employment_type,
                experience=vacancy.experience or "unknown",
                skills=list(vacancy.skills or []),
                raw_data=vacancy.raw_data,
            )
            normalized = normalize_vacancy(data)
        except Exception:  # noqa: BLE001
            logger.warning("Skip salary backfill for %s/%s", vacancy.source, vacancy.source_vacancy_id)
            continue
        if (
            vacancy.salary_from != normalized.salary_from
            or vacancy.salary_to != normalized.salary_to
            or (vacancy.currency or "").upper() != (normalized.currency or "")
        ):
            vacancy.salary_from = normalized.salary_from
            vacancy.salary_to = normalized.salary_to
            vacancy.currency = normalized.currency
            updated += 1
    if updated:
        await session.commit()
    logger.info("Renormalized %s vacancy salaries to monthly", updated)
    return updated
