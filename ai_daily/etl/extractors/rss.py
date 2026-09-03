"""RSS/Atom feed extractor."""

import asyncio
import hashlib
import logging
from calendar import timegm
from datetime import UTC, datetime

import feedparser
from trafilatura import extract, fetch_url

from ai_daily.db.models import Source
from ai_daily.etl.extractors.base import BaseExtractor
from ai_daily.etl.types import RawContent

logger = logging.getLogger(__name__)


class RSSExtractor(BaseExtractor):
    """Extract content from RSS/Atom feeds with full article fetching."""

    FETCH_DELAY = 0.5  # Seconds between article fetches
    MAX_ARTICLES_PER_FEED = 100  # Cap per feed per run
    FETCH_TIMEOUT = 15  # Article fetch timeout

    @property
    def supported_types(self) -> list[str]:
        return ["rss"]

    async def extract(self, source: Source) -> list[RawContent]:
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
                title = getattr(entry, "title", "")
                if title:
                    title = title.strip()
                if not title:
                    continue

                link = getattr(entry, "link", "")
                summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
                author = getattr(entry, "author", "") or None

                # Parse published date
                published_at = self._parse_date(entry)

                # Fetch full article content
                content = self._fetch_full_content(link)
                if not content:
                    content = summary if summary else title

                # Generate external ID from URL
                external_id = (
                    hashlib.md5(link.encode()).hexdigest()
                    if link
                    else hashlib.md5(title.encode()).hexdigest()
                )

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

    def _parse_date(self, entry) -> datetime | None:
        """Parse publication date from feed entry."""
        parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
        if parsed:
            try:
                return datetime.fromtimestamp(timegm(parsed), tz=UTC)
            except (ValueError, OverflowError, TypeError):
                pass
        return None

    def _fetch_full_content(self, url: str) -> str | None:
        """Fetch and extract full article content using trafilatura."""
        if not url:
            return None

        try:
            downloaded = fetch_url(url)
            if downloaded:
                content = extract(downloaded)
                return content
            return None
        except Exception as e:
            logger.debug(f"Failed to fetch content from {url}: {e}")
            return None

    def get_external_id(self, item: RawContent) -> str:
        """Return the item's external ID."""
        return item.external_id
