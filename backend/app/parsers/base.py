from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.schemas import VacancyData


@dataclass
class ParserConfig:
    """Runtime config passed to a vacancy source."""

    query: str | None = None
    cities: list[str] = field(default_factory=list)
    sources_settings: dict[str, Any] = field(default_factory=dict)
    max_pages: int = 5
    per_page: int = 50


class VacancySource(ABC):
    """Adapter interface for vacancy sources."""

    name: str
    display_name: str
    auto_apply_supported: bool = False

    @abstractmethod
    async def fetch_vacancies(self, config: ParserConfig) -> list[VacancyData]:
        """Fetch and return normalized vacancies from the source."""

    async def apply_to_vacancy(
        self,
        vacancy: VacancyData,
        cover_letter: str | None = None,
    ) -> dict[str, Any]:
        """
        Attempt to apply to a vacancy.
        Sources that do not support auto-apply must raise NotImplementedError.
        """
        raise NotImplementedError(f"Auto-apply is not supported for source '{self.name}'")

    def health(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "auto_apply_supported": self.auto_apply_supported,
            "status": "ready",
        }
