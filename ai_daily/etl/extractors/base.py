"""Base extractor interface for all data sources."""

from abc import ABC, abstractmethod

from ai_daily.db.models import Source
from ai_daily.etl.types import RawContent


class BaseExtractor(ABC):
    """Abstract base class for all extractors."""

    @abstractmethod
    async def extract(self, source: Source) -> list[RawContent]:
        """
        Extract raw content from the source.

        Args:
            source: The Source model instance with configuration.

        Returns:
            List of RawContent items extracted from the source.
        """
        pass

    @abstractmethod
    def get_external_id(self, item: RawContent) -> str:
        """
        Generate a unique external ID for deduplication.

        Args:
            item: The raw content item.

        Returns:
            A unique string identifier for this content.
        """
        pass

    def supports_source_type(self, source_type: str) -> bool:
        """Check if this extractor supports the given source type."""
        return source_type in self.supported_types

    @property
    @abstractmethod
    def supported_types(self) -> list[str]:
        """List of source types this extractor supports."""
        pass
