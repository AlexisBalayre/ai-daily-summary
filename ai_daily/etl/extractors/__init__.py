"""Data extractors for various sources."""

from ai_daily.etl.extractors.base import BaseExtractor
from ai_daily.etl.extractors.gmail import GmailExtractor

__all__ = ["BaseExtractor", "GmailExtractor"]
