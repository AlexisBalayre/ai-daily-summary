"""Data extractors for various sources."""

from ai_daily.etl.extractors.base import BaseExtractor
from ai_daily.etl.extractors.crawler import CrawlerExtractor
from ai_daily.etl.extractors.github import GitHubExtractor
from ai_daily.etl.extractors.gmail import GmailExtractor
from ai_daily.etl.extractors.rss import RSSExtractor

__all__ = [
    "BaseExtractor",
    "CrawlerExtractor",
    "GitHubExtractor",
    "GmailExtractor",
    "RSSExtractor",
]
