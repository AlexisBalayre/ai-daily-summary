# RSS Extractor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a dedicated RSS extractor that parses any RSS/Atom feed with just a URL, fetching full article content via trafilatura.

**Architecture:** New `RSSExtractor` class using `feedparser` for feed parsing and `trafilatura` for article extraction. Registers as `rss` source type alongside existing extractors. CLI gets streamlined `add-rss` command.

**Tech Stack:** feedparser, trafilatura, asyncio

---

## Task 1: Add Dependencies

**Files:**
- Modify: `pyproject.toml:10-36`

**Step 1: Add feedparser and trafilatura to dependencies**

In `pyproject.toml`, add these two lines to the `dependencies` list after line 16 (`beautifulsoup4`):

```toml
    "feedparser>=6.0.0",
    "trafilatura>=1.6.0",
```

**Step 2: Install dependencies**

Run: `uv sync`

Expected: Dependencies installed successfully

**Step 3: Verify imports work**

Run: `uv run python -c "import feedparser; import trafilatura; print('OK')"`

Expected: `OK`

**Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "deps: add feedparser and trafilatura for RSS extraction"
```

---

## Task 2: Write RSSExtractor Tests

**Files:**
- Create: `tests/test_rss_extractor.py`

**Step 1: Write the test file**

```python
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
        with patch("ai_daily.etl.extractors.rss.trafilatura.fetch_and_extract") as mock_fetch:
            mock_fetch.side_effect = ["Full content of article one", None]

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
        with patch("ai_daily.etl.extractors.rss.trafilatura.fetch_and_extract", return_value="Content"):
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
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_rss_extractor.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'ai_daily.etl.extractors.rss'`

**Step 3: Commit test file**

```bash
git add tests/test_rss_extractor.py
git commit -m "test: add RSS extractor tests"
```

---

## Task 3: Implement RSSExtractor

**Files:**
- Create: `ai_daily/etl/extractors/rss.py`

**Step 1: Write the RSSExtractor implementation**

```python
"""RSS/Atom feed extractor."""

import asyncio
import hashlib
import logging
from datetime import datetime
from time import mktime
from typing import List, Optional

import feedparser
import trafilatura

from ai_daily.db.models import Source
from ai_daily.etl.extractors.base import BaseExtractor
from ai_daily.etl.types import RawContent

logger = logging.getLogger(__name__)


class RSSExtractor(BaseExtractor):
    """Extract content from RSS/Atom feeds with full article fetching."""

    FETCH_DELAY = 0.5  # Seconds between article fetches
    MAX_ARTICLES_PER_FEED = 25  # Cap per feed per run
    FETCH_TIMEOUT = 15  # Article fetch timeout

    @property
    def supported_types(self) -> List[str]:
        return ["rss"]

    async def extract(self, source: Source) -> List[RawContent]:
        """Extract articles from RSS/Atom feed."""
        if not source.config:
            return []

        url = source.config.get("url")
        if not url:
            return []

        # Parse feed (feedparser auto-detects RSS 2.0 vs Atom)
        feed = feedparser.parse(url)

        if feed.bozo and not feed.entries:
            logger.warning(f"Failed to parse feed {url}: {feed.bozo_exception}")
            return []

        results = []
        for entry in feed.entries[: self.MAX_ARTICLES_PER_FEED]:
            try:
                title = entry.get("title", "").strip()
                if not title:
                    continue

                link = entry.get("link", "")
                summary = entry.get("summary", "") or entry.get("description", "")
                author = entry.get("author", "") or None

                # Parse published date
                published_at = self._parse_date(entry)

                # Fetch full article content
                content = self._fetch_full_content(link)
                if not content:
                    content = summary if summary else title

                # Generate external ID from URL
                external_id = hashlib.md5(link.encode()).hexdigest() if link else hashlib.md5(title.encode()).hexdigest()

                results.append(
                    RawContent(
                        external_id=external_id,
                        title=title,
                        content=content,
                        url=link,
                        author=author,
                        published_at=published_at,
                        source_name=source.name,
                        metadata={"feed_url": url},
                    )
                )

                # Rate limiting
                await asyncio.sleep(self.FETCH_DELAY)

            except Exception as e:
                logger.warning(f"Error processing entry from {source.name}: {e}")
                continue

        logger.info(f"Extracted {len(results)} articles from {source.name}")
        return results

    def _parse_date(self, entry) -> Optional[datetime]:
        """Parse publication date from feed entry."""
        parsed = entry.get("published_parsed") or entry.get("updated_parsed")
        if parsed:
            try:
                return datetime.fromtimestamp(mktime(parsed))
            except (ValueError, OverflowError):
                pass
        return None

    def _fetch_full_content(self, url: str) -> Optional[str]:
        """Fetch and extract full article content using trafilatura."""
        if not url:
            return None

        try:
            content = trafilatura.fetch_and_extract(url)
            return content
        except Exception as e:
            logger.debug(f"Failed to fetch content from {url}: {e}")
            return None

    def get_external_id(self, item: RawContent) -> str:
        """Return the item's external ID."""
        return item.external_id
```

**Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/test_rss_extractor.py -v`

Expected: All 6 tests PASS

**Step 3: Commit implementation**

```bash
git add ai_daily/etl/extractors/rss.py
git commit -m "feat: add RSSExtractor for RSS/Atom feed parsing"
```

---

## Task 4: Register RSSExtractor in Pipeline

**Files:**
- Modify: `ai_daily/etl/extractors/__init__.py:1-13`
- Modify: `ai_daily/etl/pipeline.py:11,18-22`

**Step 1: Export RSSExtractor from extractors package**

Replace `ai_daily/etl/extractors/__init__.py` with:

```python
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
```

**Step 2: Register in pipeline EXTRACTORS dict**

In `ai_daily/etl/pipeline.py`, update line 11 to include RSSExtractor import:

```python
from ai_daily.etl.extractors import BaseExtractor, CrawlerExtractor, GitHubExtractor, GmailExtractor, RSSExtractor
```

Update lines 18-22 to add rss mapping:

```python
EXTRACTORS: Dict[str, Type[BaseExtractor]] = {
    "newsletter": GmailExtractor,
    "github": GitHubExtractor,
    "crawler": CrawlerExtractor,
    "rss": RSSExtractor,
}
```

**Step 3: Verify all tests still pass**

Run: `uv run pytest -v`

Expected: All 15+ tests PASS

**Step 4: Commit**

```bash
git add ai_daily/etl/extractors/__init__.py ai_daily/etl/pipeline.py
git commit -m "feat: register RSSExtractor in ETL pipeline"
```

---

## Task 5: Add CLI Commands

**Files:**
- Modify: `ai_daily/cli.py:37,48-49,180-204`

**Step 1: Add 'rss' to run command choices**

In `ai_daily/cli.py`, change line 37 from:

```python
@click.argument("job_type", type=click.Choice(["gmail", "github", "crawlers", "all"]))
```

to:

```python
@click.argument("job_type", type=click.Choice(["gmail", "github", "crawlers", "rss", "all"]))
```

**Step 2: Add 'rss' to type_map**

Change lines 48-49 from:

```python
            type_map = {"gmail": "newsletter", "github": "github", "crawlers": "crawler"}
            metrics = await pipeline.run_all(source_types=[type_map[job_type]])
```

to:

```python
            type_map = {"gmail": "newsletter", "github": "github", "crawlers": "crawler", "rss": "rss"}
            metrics = await pipeline.run_all(source_types=[type_map[job_type]])
```

**Step 3: Add 'rss' to source add choices**

Change line 181 from:

```python
@click.argument("source_type", type=click.Choice(["newsletter", "github", "crawler"]))
```

to:

```python
@click.argument("source_type", type=click.Choice(["newsletter", "github", "crawler", "rss"]))
```

**Step 4: Add streamlined add-rss command**

After the `source_add` function (after line 204), add:

```python
@source.command("add-rss")
@click.argument("name")
@click.argument("url")
def source_add_rss(name: str, url: str):
    """Add an RSS feed source (simplified - just name and URL)."""
    with get_session() as session:
        src = Source(
            type="rss",
            name=name,
            config={"url": url},
            enabled=True,
        )
        session.add(src)
        session.commit()
        console.print(f"[green]Added RSS source: {name} (ID: {src.id})[/green]")
```

**Step 5: Test CLI commands work**

Run: `uv run ai-daily run --help`

Expected: Shows `{gmail,github,crawlers,rss,all}` in help text

Run: `uv run ai-daily source add --help`

Expected: Shows `{newsletter,github,crawler,rss}` in help text

Run: `uv run ai-daily source add-rss --help`

Expected: Shows `Usage: ai-daily source add-rss [OPTIONS] NAME URL`

**Step 6: Run all tests**

Run: `uv run pytest -v`

Expected: All tests PASS

**Step 7: Commit**

```bash
git add ai_daily/cli.py
git commit -m "feat: add CLI commands for RSS sources"
```

---

## Task 6: Add CLI Tests

**Files:**
- Create: `tests/test_cli_rss.py`

**Step 1: Write CLI tests**

```python
"""Tests for RSS CLI commands."""

import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from ai_daily.cli import main


@pytest.fixture
def runner():
    return CliRunner()


def test_run_rss_in_choices(runner):
    """'rss' should be a valid choice for run command."""
    result = runner.invoke(main, ["run", "--help"])
    assert "rss" in result.output


def test_source_add_rss_in_choices(runner):
    """'rss' should be a valid choice for source add command."""
    result = runner.invoke(main, ["source", "add", "--help"])
    assert "rss" in result.output


def test_source_add_rss_command_exists(runner):
    """source add-rss command should exist."""
    result = runner.invoke(main, ["source", "add-rss", "--help"])
    assert result.exit_code == 0
    assert "NAME" in result.output
    assert "URL" in result.output


@patch("ai_daily.cli.get_session")
def test_source_add_rss_creates_source(mock_get_session, runner):
    """source add-rss should create an RSS source."""
    mock_session = MagicMock()
    mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

    # Mock the source to have an ID after add
    def set_id(src):
        src.id = 42
    mock_session.add.side_effect = set_id

    result = runner.invoke(main, [
        "source", "add-rss",
        "Test Feed",
        "https://example.com/feed.xml"
    ])

    assert result.exit_code == 0
    assert "Added RSS source: Test Feed" in result.output

    # Verify source was created with correct config
    added_source = mock_session.add.call_args[0][0]
    assert added_source.type == "rss"
    assert added_source.name == "Test Feed"
    assert added_source.config == {"url": "https://example.com/feed.xml"}
    assert added_source.enabled is True
```

**Step 2: Run CLI tests**

Run: `uv run pytest tests/test_cli_rss.py -v`

Expected: All 4 tests PASS

**Step 3: Run full test suite**

Run: `uv run pytest -v`

Expected: All tests PASS

**Step 4: Commit**

```bash
git add tests/test_cli_rss.py
git commit -m "test: add CLI tests for RSS commands"
```

---

## Task 7: Add Initial RSS Feeds

**Prerequisites:** Requires a running database. Skip if no database available.

**Step 1: Add the 7 tech RSS feeds**

Run each command:

```bash
uv run ai-daily source add-rss "Computerworld" "https://www.computerworld.com/feed/"
uv run ai-daily source add-rss "MIT Technology Review" "https://www.technologyreview.com/feed/"
uv run ai-daily source add-rss "Wired AI" "https://www.wired.com/feed/tag/ai/latest/rss"
uv run ai-daily source add-rss "Ars Technica Tech Lab" "https://feeds.arstechnica.com/arstechnica/technology-lab"
uv run ai-daily source add-rss "TechRadar" "https://www.techradar.com/feeds.xml"
uv run ai-daily source add-rss "TechRadar News" "https://www.techradar.com/feeds/articletype/news"
uv run ai-daily source add-rss "The Verge" "https://www.theverge.com/rss/index.xml"
```

**Step 2: Verify sources added**

Run: `uv run ai-daily source list`

Expected: Shows 7 RSS sources with type "rss"

**Step 3: Test extraction with one feed**

Run: `uv run ai-daily run rss`

Expected: ETL completes, shows articles processed/created

---

## Summary

| Task | Description | Files Changed |
|------|-------------|---------------|
| 1 | Add dependencies | pyproject.toml |
| 2 | Write extractor tests | tests/test_rss_extractor.py |
| 3 | Implement RSSExtractor | ai_daily/etl/extractors/rss.py |
| 4 | Register in pipeline | extractors/__init__.py, pipeline.py |
| 5 | Add CLI commands | cli.py |
| 6 | Add CLI tests | tests/test_cli_rss.py |
| 7 | Add initial feeds | (database only) |

**Total commits:** 6 (excluding feed setup)
