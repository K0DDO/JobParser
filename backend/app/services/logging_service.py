from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SystemLog, Notification


async def add_log(
    session: AsyncSession,
    message: str,
    *,
    level: str = "info",
    category: str = "system",
    details: dict | None = None,
) -> SystemLog:
    entry = SystemLog(level=level, category=category, message=message, details=details)
    session.add(entry)
    await session.flush()
    return entry


async def add_notification(
    session: AsyncSession,
    title: str,
    message: str,
) -> Notification:
    note = Notification(title=title, message=message)
    session.add(note)
    await session.flush()
    return note
