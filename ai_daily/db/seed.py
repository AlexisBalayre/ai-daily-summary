"""Seed database with initial sources."""

import json
import logging
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from ai_daily.config import config
from ai_daily.db import Source, get_session

logger = logging.getLogger(__name__)


def seed_sources():
    """Seed sources from config.json."""
    config_file = config.config_file

    if not config_file.exists():
        logger.info("No config.json found, skipping source seeding")
        return

    try:
        with open(config_file) as f:
            data = json.load(f)
    except FileNotFoundError:
        logger.error("Config file not found: %s", config_file)
        return
    except PermissionError:
        logger.error("Permission denied when reading config file: %s", config_file)
        return
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in config file %s: %s", config_file, e)
        return

    whitelist = data.get("whitelist", [])

    with get_session() as session:
        # Check if newsletter source exists
        existing = session.query(Source).filter(Source.type == "newsletter").first()

        if not existing:
            # Create newsletter source with whitelist
            newsletter_source = Source(
                type="newsletter",
                name="Email Newsletters",
                config={"whitelist": whitelist, "days_back": 2},
                enabled=True,
            )
            session.add(newsletter_source)
            logger.info("Created newsletter source with %d whitelisted senders", len(whitelist))

        # Check if GitHub source exists
        existing_github = session.query(Source).filter(Source.type == "github").first()

        if not existing_github:
            github_source = Source(
                type="github",
                name="GitHub Trending",
                config={"fetch_trending": True, "fetch_explore": True},
                enabled=True,
            )
            session.add(github_source)
            logger.info("Created GitHub source")

        # RSS feeds (release/news monitoring). Idempotent by (type, name).
        for feed in data.get("rss_feeds", []):
            name, url = feed.get("name"), feed.get("url")
            if not name or not url:
                continue
            exists = session.query(Source).filter(
                Source.type == "rss", Source.name == name
            ).first()
            if exists:
                continue
            session.add(Source(type="rss", name=name, config={"url": url}, enabled=True))
            logger.info("Created RSS source: %s", name)

        # Crawlers (SSR pages without an RSS feed, e.g. Anthropic news).
        for crawler in data.get("crawlers", []):
            name, url = crawler.get("name"), crawler.get("url")
            if not name or not url:
                continue
            exists = session.query(Source).filter(
                Source.type == "crawler", Source.name == name
            ).first()
            if exists:
                continue
            cfg = {
                "url": url,
                "selectors": crawler.get("selectors", {}),
                "content_mode": crawler.get("content_mode", "summary_only"),
            }
            session.add(Source(type="crawler", name=name, config=cfg, enabled=True))
            logger.info("Created crawler source: %s", name)

        try:
            session.commit()
            logger.info("Database seeding complete")
        except SQLAlchemyError as e:
            logger.error("Database error during seeding: %s", e)
            session.rollback()
            raise


if __name__ == "__main__":
    seed_sources()
