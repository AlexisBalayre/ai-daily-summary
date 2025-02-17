import os
import json
from datetime import datetime
from typing import List, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum

from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
from pathlib import Path

from .utils import logger

load_dotenv()  # Load environment variables


class RepositoryType(Enum):
    TRENDING = "trending"
    EXPLORE = "explore"


@dataclass
class TrendingRepository:
    """Data class to store trending repository information"""
    author: str
    name: str
    description: str
    stars: int
    forks: int
    url: str
    language: str
    collected_at: str = None

    def __post_init__(self):
        self.collected_at = datetime.now().isoformat()


@dataclass
class ExploreRepository:
    """Data class to store explore repository information"""
    author: str
    name: str
    description: str
    stars: int
    url: str
    language: str
    updated_at: str
    collected_at: str = None

    def __post_init__(self):
        self.collected_at = datetime.now().isoformat()


class GithubScraper:
    BASE_URL = "https://github.com"
    TRENDING_URL = f"{BASE_URL}/trending"
    EXPLORE_URL = f"{BASE_URL}/explore"

    def __init__(self):
        self._init_session()
        self._init_data_directory()

    def _init_session(self) -> None:
        """Initialize requests session with required headers"""
        self.session = requests.Session()
        self.session.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            "Cookie": os.getenv("GITHUB_COOKIE"),
            "Host": "github.com",
            "Referer": self.TRENDING_URL,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Sec-GPC": "1",
            "priority": "u=0, i",
        }

    def _init_data_directory(self) -> None:
        """Create data directory if it doesn't exist"""
        self.data_dir = Path("data/repositories")
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _parse_numeric_value(self, text: str) -> int:
        """Parse numeric values from text, removing commas and converting to int"""
        try:
            text = text.strip().split()[0].replace(",", "")
            if "k" in text:
                return int(float(text[:-1]) * 1000)
            return int(text)
        except (ValueError, IndexError):
            return 0

    def _parse_trending_repository(self, repo_element: BeautifulSoup) -> Optional[TrendingRepository]:
        """Parse repository data from a trending page BeautifulSoup element"""
        try:
            title_element = repo_element.select_one("h2.h3")
            return TrendingRepository(
                author=title_element.select_one("a").text.strip().split("/")[0],
                name=title_element.select_one("a").text.strip().split("/")[1],
                description=repo_element.select_one("p.color-fg-muted").text.strip() if repo_element.select_one("p.color-fg-muted") else "",
                stars=self._parse_numeric_value(repo_element.select_one("a.Link--muted").text),
                forks=self._parse_numeric_value(repo_element.select("a.Link--muted")[1].text),
                url=f"{self.BASE_URL}{title_element.select_one('a')['href']}",
                language=repo_element.select('span[itemprop="programmingLanguage"]')[0].text.strip() 
                if repo_element.select('span[itemprop="programmingLanguage"]') else "Unknown"
            )
        except Exception as e:
            logger.error(f"Error parsing trending repository: {str(e)}")
            return None

    def _parse_explore_repository(self, repo_element: BeautifulSoup) -> Optional[ExploreRepository]:
        """Parse repository data from an explore page BeautifulSoup element"""
        try:
            title_element = repo_element.select_one("h3")
            if not title_element:
                return None

            full_name_elements = title_element.select("a")
            if len(full_name_elements) != 2:
                return None

            author = full_name_elements[0].text.strip()
            name = full_name_elements[1].text.strip()
            url = f"{self.BASE_URL}{full_name_elements[1]['href']}"

            return ExploreRepository(
                author=author,
                name=name,
                description=repo_element.select_one("p.color-fg-muted").text.strip() 
                if repo_element.select_one("p.color-fg-muted") else "",
                stars=self._parse_numeric_value(
                    repo_element.select_one('span[id="repo-stars-counter-star"]').text
                ) if repo_element.select_one('span[id="repo-stars-counter-star"]') else 0,
                url=url,
                language=repo_element.select_one("span[itemprop='programmingLanguage']").text.strip()
                if repo_element.select_one("span[itemprop='programmingLanguage']") else "Unknown",
                updated_at=repo_element.select_one("relative-time")["datetime"]
                if repo_element.select_one("relative-time") else ""
            )
        except Exception as e:
            logger.error(f"Error parsing explore repository: {str(e)}")
            return None

    def _save_repositories(
        self, 
        repositories: Union[List[TrendingRepository], List[ExploreRepository]], 
        repo_type: RepositoryType
    ) -> None:
        """Save repositories to a JSON file with timestamp in filename"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.data_dir / f"{repo_type.value}_repositories_{timestamp}.json"

        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "type": repo_type.value,
                        "timestamp": datetime.now().isoformat(),
                        "count": len(repositories),
                        "repositories": [asdict(repo) for repo in repositories],
                    },
                    f,
                    indent=2,
                    ensure_ascii=False,
                )
            logger.info(f"Successfully saved {len(repositories)} {repo_type.value} repositories to {filename}")
        except Exception as e:
            logger.error(f"Error saving {repo_type.value} repositories to JSON: {str(e)}")

    def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a GitHub page"""
        try:
            response = self.session.get(url)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except requests.RequestException as e:
            logger.error(f"Error fetching page {url}: {str(e)}")
            return None

    def fetch_trending_repositories(self) -> List[TrendingRepository]:
        """Fetch and parse trending repositories from GitHub"""
        repositories = []
        
        if soup := self._fetch_page(self.TRENDING_URL):
            for repo_element in soup.select("article.Box-row"):
                if repo := self._parse_trending_repository(repo_element):
                    repositories.append(repo)

            self._save_repositories(repositories, RepositoryType.TRENDING)
        
        return repositories

    def fetch_explore_repositories(self) -> List[ExploreRepository]:
        """Fetch and parse repositories from GitHub's explore page"""
        repositories = []
        
        if soup := self._fetch_page(self.EXPLORE_URL):
            for repo_element in soup.select("article"):
                if repo := self._parse_explore_repository(repo_element):
                    repositories.append(repo)

            self._save_repositories(repositories, RepositoryType.EXPLORE)
        
        return repositories


if __name__ == "__main__":
    scraper = GithubScraper()

    # Fetch trending repositories
    trending_repos = scraper.fetch_trending_repositories()
    print(f"Collected {len(trending_repos)} trending repositories")

    # Fetch explore repositories
    explore_repos = scraper.fetch_explore_repositories()
    print(f"Collected {len(explore_repos)} explore repositories")