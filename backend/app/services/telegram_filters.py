"""Telegram filter presets (roles / work formats) shared by bot UI and sync."""

from __future__ import annotations

from typing import Any

TELEGRAM_ROLES: list[str] = [
    "Backend",
    "Frontend",
    "Fullstack",
    "Mobile",
    "Android",
    "iOS",
    "QA",
    "DevOps",
    "SRE",
    "Data",
    "ML",
    "Analyst",
    "Architect",
    "Manager",
    "Embedded",
    "Security",
    "Python",
    "Java",
    "Go",
]

TELEGRAM_WORK_FORMATS: list[tuple[str, str]] = [
    ("remote", "Удалёнка"),
    ("hybrid", "Гибрид"),
    ("office", "Офис"),
]


def vacancy_matches_telegram_filters(
    vacancy: Any,
    *,
    roles: list[str] | None,
    work_formats: list[str] | None,
) -> bool:
    """True if vacancy fits Telegram selections. Empty roles => no notify."""
    selected_roles = [r for r in (roles or []) if r and r.strip()]
    if not selected_roles:
        return False

    title = (getattr(vacancy, "title", None) or "").lower()
    skills_blob = " ".join(getattr(vacancy, "skills", None) or []).lower()
    blob = f"{title} {skills_blob}"
    if not any(role.lower().strip() in blob for role in selected_roles):
        return False

    selected_formats = [f for f in (work_formats or []) if f and f.strip()]
    if selected_formats:
        fmt = (getattr(vacancy, "work_format", None) or "unknown").lower()
        remote = bool(getattr(vacancy, "remote", False))
        if remote and "remote" in selected_formats:
            return True
        if fmt not in {f.lower() for f in selected_formats}:
            return False
    return True
