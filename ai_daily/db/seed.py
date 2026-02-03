"""Seed database with initial sources."""

import json
from pathlib import Path

from ai_daily.config import config
from ai_daily.db import Source, get_session


def seed_sources():
    """Seed sources from config.json."""
    config_file = config.config_file

    if not config_file.exists():
        print("No config.json found, skipping source seeding")
        return

    with open(config_file) as f:
        data = json.load(f)

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
            print(f"Created newsletter source with {len(whitelist)} whitelisted senders")

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
            print("Created GitHub source")

        session.commit()
        print("Database seeding complete")


if __name__ == "__main__":
    seed_sources()
