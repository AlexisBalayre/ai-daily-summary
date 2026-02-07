"""Tests for RSS extractor."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from ai_daily.db.models import Source
from ai_daily.etl.extractors.rss import RSSExtractor
from ai_daily.etl.types import RawContent


@pytest.fixture
def rss_source():
    """Create a mock RSS source."""
    source = MagicMock(spec=Source)
    source.id = 1
    source.name = "Test RSS Feed"
    source.config = {"url": "https://example.com/feed.xml"}
    return source


@pytest.fixture
def sample_feed():
    """Sample parsed feed data."""
    feed = MagicMock()
    feed.entries = [
        MagicMock(
            title="Article One",
            link="https://example.com/article-1",
            summary="Summary of article one",
            author="Author One",
            published_parsed=(2026, 2, 7, 12, 0, 0, 0, 0, 0),
        ),
        MagicMock(
            title="Article Two",
            link="https://example.com/article-2",
            summary="Summary of article two",
            author="",
            published_parsed=None,
        ),
    ]
    return feed


def test_rss_extractor_supported_types():
    """RSSExtractor should support 'rss' type."""
    extractor = RSSExtractor()
    assert extractor.supported_types == ["rss"]


def test_rss_extractor_supports_rss_type():
    """RSSExtractor.supports_source_type should return True for 'rss'."""
    extractor = RSSExtractor()
    assert extractor.supports_source_type("rss") is True
    assert extractor.supports_source_type("crawler") is False


@pytest.mark.asyncio
async def test_rss_extractor_returns_empty_for_missing_url(rss_source):
    """Should return empty list if source has no URL configured."""
    rss_source.config = {}
    extractor = RSSExtractor()

    result = await extractor.extract(rss_source)

    assert result == []


@pytest.mark.asyncio
async def test_rss_extractor_parses_feed_entries(rss_source, sample_feed):
    """Should parse feed entries and fetch full content."""
    extractor = RSSExtractor()

    with patch("ai_daily.etl.extractors.rss.feedparser.parse", return_value=sample_feed):
        with patch("ai_daily.etl.extractors.rss.fetch_url") as mock_fetch_url:
            with patch("ai_daily.etl.extractors.rss.extract") as mock_extract:
                mock_fetch_url.side_effect = ["<html>content1</html>", None]
                mock_extract.side_effect = ["Full content of article one", None]

                result = await extractor.extract(rss_source)

    assert len(result) == 2

    # First article - trafilatura succeeded
    assert result[0].title == "Article One"
    assert result[0].url == "https://example.com/article-1"
    assert result[0].content == "Full content of article one"
    assert result[0].author == "Author One"
    assert result[0].source_name == "Test RSS Feed"

    # Second article - trafilatura failed, falls back to summary
    assert result[1].title == "Article Two"
    assert result[1].content == "Summary of article two"
    assert result[1].author is None


@pytest.mark.asyncio
async def test_rss_extractor_skips_entries_without_title(rss_source):
    """Should skip entries that have no title."""
    feed = MagicMock()
    feed.entries = [
        MagicMock(title="", link="https://example.com/1", summary="No title"),
        MagicMock(title="Valid Title", link="https://example.com/2", summary="Has title"),
    ]

    extractor = RSSExtractor()

    with patch("ai_daily.etl.extractors.rss.feedparser.parse", return_value=feed):
        with patch("ai_daily.etl.extractors.rss.fetch_url", return_value="<html>content</html>"):
            with patch("ai_daily.etl.extractors.rss.extract", return_value="Content"):
                result = await extractor.extract(rss_source)

    assert len(result) == 1
    assert result[0].title == "Valid Title"


def test_rss_extractor_get_external_id():
    """get_external_id should return the item's external_id."""
    extractor = RSSExtractor()
    item = RawContent(
        external_id="abc123",
        title="Test",
        content="Content",
    )

    assert extractor.get_external_id(item) == "abc123"
