import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.session import Base
from app.models import AppSettings, SearchProfile, SourceConfig, Vacancy


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    # SQLite doesn't support ARRAY/JSONB — use JSON for tests via type adaptation
    # For unit tests we mostly test pure functions; DB tests use simplified models carefully.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as s:
        yield s
    await engine.dispose()


@pytest.fixture
def sample_vacancy_kwargs():
    return {
        "source": "hh",
        "source_vacancy_id": "100",
        "url": "https://hh.ru/vacancy/100",
        "title": "Python Backend Developer",
        "company": "Acme",
        "description": "FastAPI PostgreSQL Redis Docker",
        "salary_from": 180000,
        "salary_to": 250000,
        "currency": "RUB",
        "city": "Москва",
        "remote": True,
        "work_format": "remote",
        "experience": "between_1_and_3",
        "skills": ["Python", "FastAPI", "PostgreSQL"],
        "status": "new",
    }
