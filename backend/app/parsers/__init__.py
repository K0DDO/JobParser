from app.parsers.arbeitnow import ArbeitnowSource
from app.parsers.base import VacancySource
from app.parsers.getmatch import GetMatchSource
from app.parsers.greenhouse import GreenhouseSource
from app.parsers.habr import HabrSource
from app.parsers.hh import HHSource
from app.parsers.himalayas import HimalayasSource
from app.parsers.hirify import HirifySource
from app.parsers.jobicy import JobicySource
from app.parsers.remoteok import RemoteOKSource
from app.parsers.remotive import RemotiveSource
from app.parsers.talanto import TalantoSource
from app.parsers.weworkremotely import WeWorkRemotelySource
from app.parsers.workingnomads import WorkingNomadsSource


def get_all_sources() -> dict[str, VacancySource]:
    sources: list[VacancySource] = [
        HHSource(),
        HabrSource(),
        HirifySource(),
        TalantoSource(),
        GetMatchSource(),
        RemoteOKSource(),
        RemotiveSource(),
        HimalayasSource(),
        JobicySource(),
        ArbeitnowSource(),
        WeWorkRemotelySource(),
        WorkingNomadsSource(),
        GreenhouseSource(),
    ]
    return {s.name: s for s in sources}


def get_source(name: str) -> VacancySource | None:
    return get_all_sources().get(name)
