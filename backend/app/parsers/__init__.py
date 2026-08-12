from app.parsers.base import VacancySource
from app.parsers.getmatch import GetMatchSource
from app.parsers.habr import HabrSource
from app.parsers.hh import HHSource
from app.parsers.hirify import HirifySource
from app.parsers.talanto import TalantoSource


def get_all_sources() -> dict[str, VacancySource]:
    sources: list[VacancySource] = [
        HHSource(),
        HabrSource(),
        HirifySource(),
        TalantoSource(),
        GetMatchSource(),
    ]
    return {s.name: s for s in sources}


def get_source(name: str) -> VacancySource | None:
    return get_all_sources().get(name)
