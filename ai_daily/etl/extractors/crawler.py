"""Web crawler extractor for monitoring websites."""

import hashlib
import re
from datetime import datetime
from typing import Any, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from trafilatura import extract, fetch_url

from ai_daily.db.models import Source

# author is VARCHAR(255) in the DB; keep a margin below that.
MAX_AUTHOR_LEN = 250
from ai_daily.etl.extractors.base import BaseExtractor
from ai_daily.etl.types import RawContent


class CrawlerExtractor(BaseExtractor):
    """Extract content from websites using configurable selectors."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

    @property
    def supported_types(self) -> List[str]:
        return ["crawler"]

    def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a page."""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except requests.RequestException:
            return None

    def _extract_attribute(self, element: Any, selector: str) -> str:
        """Extract text or attribute from element based on selector.

        Selector format:
        - "selector" -> get text content
        - "selector@attr" -> get attribute value
        """
        if "@" in selector:
            css_selector, attr = selector.rsplit("@", 1)
            target = element.select_one(css_selector) if css_selector else element
            if target:
                return target.get(attr, "")
        else:
            target = element.select_one(selector) if selector else element
            if target:
                return target.get_text(strip=True)
        return ""

    def _fetch_full_content(self, url: str, content_selector: Optional[str]) -> str:
        """Fetch full article content from URL.

        With a CSS content_selector, extract that element. Without one, fall back
        to trafilatura's generic article extraction — this is what makes SSR pages
        (e.g. Anthropic news) usable, since hashed CSS-module class names are too
        brittle to target directly.
        """
        if content_selector:
            soup = self._fetch_page(url)
            if not soup:
                return ""
            content_elem = soup.select_one(content_selector)
            return content_elem.get_text(strip=True) if content_elem else ""

        try:
            downloaded = fetch_url(url)
            if downloaded:
                return extract(downloaded) or ""
        except Exception:
            pass
        return ""

    def _trafilatura_extract(self, url: str) -> tuple[str, str]:
        """Return (clean_title, content) for an article page.

        Used for SSR sources with no CSS content selector: the list-page card
        text is a noisy blob, so we take the article page's own og:title/title
        and trafilatura-extracted body.
        """
        try:
            downloaded = fetch_url(url)
            if not downloaded:
                return "", ""
            content = extract(downloaded) or ""
            title = ""
            soup = BeautifulSoup(downloaded, "html.parser")
            og = soup.find("meta", attrs={"property": "og:title"})
            if og and og.get("content"):
                title = og["content"].strip()
            elif soup.title and soup.title.string:
                title = soup.title.string.strip()
            # Drop a trailing site suffix like " \ Anthropic" or " | Anthropic".
            if title:
                title = re.split(r"\s[\\|]\s", title)[0].strip()
            return title, content
        except Exception:
            return "", ""

    @staticmethod
    def _title_from_slug(link: str) -> str:
        """Fallback title from a URL slug: /news/claude-sonnet-5 -> 'Claude Sonnet 5'."""
        slug = link.rstrip("/").rsplit("/", 1)[-1]
        return slug.replace("-", " ").replace("_", " ").strip().title()

    async def extract(self, source: Source) -> List[RawContent]:
        """Extract content from configured website."""
        if not source.config:
            return []

        url = source.config.get("url")
        if not url:
            return []

        selectors = source.config.get("selectors", {})
        items_selector = selectors.get("items")
        if not items_selector:
            return []

        title_selector = selectors.get("title", "")
        link_selector = selectors.get("link", "")
        description_selector = selectors.get("description", "")
        author_selector = selectors.get("author", "")
        date_selector = selectors.get("date", "")

        content_mode = source.config.get("content_mode", "summary_only")
        content_selector = selectors.get("content", "")

        soup = self._fetch_page(url)
        if not soup:
            return []

        items = soup.select(items_selector)
        raw_contents = []

        for item in items:
            try:
                title = self._extract_attribute(item, title_selector)

                link = self._extract_attribute(item, link_selector)
                if link and not link.startswith("http"):
                    link = urljoin(url, link)

                # Optional fields come ONLY from an explicit selector. An empty
                # selector must not fall back to the whole element's text — that
                # blob overflows author VARCHAR(255) and crashes the ETL insert.
                description = self._extract_attribute(item, description_selector) if description_selector else ""
                author = self._extract_attribute(item, author_selector) if author_selector else ""
                date_str = self._extract_attribute(item, date_selector) if date_selector else ""

                content = ""
                page_title = ""
                if content_mode == "fetch_full" and link:
                    if content_selector:
                        content = self._fetch_full_content(link, content_selector)
                    else:
                        page_title, content = self._trafilatura_extract(link)

                # Prefer the article page's clean title when the card gave nothing
                # or a whole-card text blob; last resort is the URL slug.
                if page_title and (not title or len(title) > 120):
                    title = page_title
                if link and (not title or len(title) > 120):
                    title = self._title_from_slug(link)
                if not title:
                    continue

                if not content:
                    content = description or title

                if author and len(author) > MAX_AUTHOR_LEN:
                    author = author[:MAX_AUTHOR_LEN]

                external_id = hashlib.md5((link or title).encode()).hexdigest()

                raw_contents.append(RawContent(
                    external_id=external_id,
                    title=title,
                    content=content,
                    url=link,
                    author=author if author else None,
                    published_at=datetime.utcnow(),
                    source_name=source.name,
                    metadata={
                        "crawler_url": url,
                        "date_string": date_str,
                    }
                ))
            except Exception:
                continue

        return raw_contents

    def get_external_id(self, item: RawContent) -> str:
        """Use computed hash as external ID."""
        return item.external_id
