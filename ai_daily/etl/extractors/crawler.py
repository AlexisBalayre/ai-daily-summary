"""Web crawler extractor for monitoring websites."""

import hashlib
from datetime import datetime
from typing import Any, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from trafilatura import extract, fetch_url

from ai_daily.db.models import Source
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
                if not title:
                    continue

                link = self._extract_attribute(item, link_selector)
                if link and not link.startswith("http"):
                    link = urljoin(url, link)

                description = self._extract_attribute(item, description_selector)
                author = self._extract_attribute(item, author_selector)
                date_str = self._extract_attribute(item, date_selector)

                if content_mode == "fetch_full" and link:
                    content = self._fetch_full_content(link, content_selector)
                    if not content:
                        content = description
                else:
                    content = description

                if not content:
                    content = title

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
