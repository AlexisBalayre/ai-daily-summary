"""GitHub trending repositories extractor."""

import hashlib
import os
from datetime import datetime
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from ai_daily.db.models import Source
from ai_daily.etl.extractors.base import BaseExtractor
from ai_daily.etl.types import RawContent


class GitHubExtractor(BaseExtractor):
    """Extract trending repositories from GitHub."""

    BASE_URL = "https://github.com"
    TRENDING_URL = f"{BASE_URL}/trending"
    EXPLORE_URL = f"{BASE_URL}/explore"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Cookie": os.getenv("GITHUB_COOKIE", ""),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

    @property
    def supported_types(self) -> List[str]:
        return ["github"]

    def _parse_numeric(self, text: str) -> int:
        """Parse numeric values like '1.2k' into integers."""
        try:
            text = text.strip().split()[0].replace(",", "")
            if "k" in text.lower():
                return int(float(text.lower().replace("k", "")) * 1000)
            return int(text)
        except (ValueError, IndexError):
            return 0

    def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a page."""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except requests.RequestException:
            return None

    def _fetch_repo_description(self, url: str) -> str:
        """Fetch description from repo page if not available."""
        if soup := self._fetch_page(url):
            meta = soup.find("meta", {"name": "description"})
            if meta:
                content = meta.get("content", "").strip()
                if " - " in content:
                    parts = content.rsplit(" - ", 1)
                    if len(parts) == 2 and "/" in parts[1]:
                        content = parts[0]
                return content
        return ""

    def _extract_trending(self, soup: BeautifulSoup) -> List[RawContent]:
        """Extract trending repositories."""
        repos = []

        for article in soup.select("article.Box-row"):
            try:
                title_elem = article.select_one("h2.h3 a")
                if not title_elem:
                    continue

                full_name = title_elem.text.strip().replace("\n", "").replace(" ", "")
                parts = full_name.split("/")
                if len(parts) != 2:
                    continue

                author, name = parts
                url = f"{self.BASE_URL}{title_elem['href']}"

                desc_elem = article.select_one("p.color-fg-muted")
                description = desc_elem.text.strip() if desc_elem else ""
                if "There was an error" in description:
                    description = ""
                if not description:
                    description = self._fetch_repo_description(url)

                stars_elem = article.select_one("a.Link--muted")
                stars = self._parse_numeric(stars_elem.text) if stars_elem else 0

                forks_elems = article.select("a.Link--muted")
                forks = self._parse_numeric(forks_elems[1].text) if len(forks_elems) > 1 else 0

                lang_elem = article.select_one('span[itemprop="programmingLanguage"]')
                language = lang_elem.text.strip() if lang_elem else "Unknown"

                content = f"{description}\n\nLanguage: {language}\nStars: {stars:,}\nForks: {forks:,}"

                repos.append(RawContent(
                    external_id=hashlib.md5(url.encode()).hexdigest(),
                    title=f"{author}/{name}",
                    content=content,
                    url=url,
                    author=author,
                    published_at=datetime.utcnow(),
                    source_name="github_trending",
                    metadata={
                        "stars": stars,
                        "forks": forks,
                        "language": language,
                        "repo_type": "trending",
                    }
                ))
            except Exception:
                continue

        return repos

    def _extract_explore(self, soup: BeautifulSoup) -> List[RawContent]:
        """Extract explore repositories."""
        repos = []

        for article in soup.select("article"):
            try:
                title_elem = article.select_one("h3")
                if not title_elem:
                    continue

                links = title_elem.select("a")
                if len(links) != 2:
                    continue

                author = links[0].text.strip()
                name = links[1].text.strip()
                url = f"{self.BASE_URL}{links[1]['href']}"

                desc_elem = article.select_one("p.color-fg-muted")
                description = desc_elem.text.strip() if desc_elem else ""
                if "There was an error" in description:
                    description = ""
                if not description:
                    description = self._fetch_repo_description(url)

                stars_elem = article.select_one('span[id="repo-stars-counter-star"]')
                stars = self._parse_numeric(stars_elem.text) if stars_elem else 0

                lang_elem = article.select_one('span[itemprop="programmingLanguage"]')
                language = lang_elem.text.strip() if lang_elem else "Unknown"

                content = f"{description}\n\nLanguage: {language}\nStars: {stars:,}"

                repos.append(RawContent(
                    external_id=hashlib.md5(url.encode()).hexdigest(),
                    title=f"{author}/{name}",
                    content=content,
                    url=url,
                    author=author,
                    published_at=datetime.utcnow(),
                    source_name="github_explore",
                    metadata={
                        "stars": stars,
                        "language": language,
                        "repo_type": "explore",
                    }
                ))
            except Exception:
                continue

        return repos

    async def extract(self, source: Source) -> List[RawContent]:
        """Extract repositories from GitHub."""
        repos = []

        fetch_trending = source.config.get("fetch_trending", True) if source.config else True
        fetch_explore = source.config.get("fetch_explore", True) if source.config else True

        if fetch_trending:
            if soup := self._fetch_page(self.TRENDING_URL):
                repos.extend(self._extract_trending(soup))

        if fetch_explore:
            if soup := self._fetch_page(self.EXPLORE_URL):
                repos.extend(self._extract_explore(soup))

        return repos

    def get_external_id(self, item: RawContent) -> str:
        """Use URL hash as external ID."""
        return item.external_id
