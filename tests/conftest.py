"""Pytest configuration and fixtures."""

import json
import pytest
from sqlalchemy import create_engine, event, Text, delete
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Boolean, DateTime
from datetime import datetime, UTC
from typing import Optional


# Create simplified models that work with SQLite
# Note: Prefix with "Sqlite" instead of "Test" to avoid pytest collection warnings
class SqliteBase(DeclarativeBase):
    """Base class for SQLite-compatible models."""
    pass


class SqliteSource(SqliteBase):
    """Simplified Source model for testing with SQLite."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    config: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Store JSON as text
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    def set_config(self, config_dict: dict) -> None:
        """Set config from dict."""
        self.config = json.dumps(config_dict)

    def get_config(self) -> dict:
        """Get config as dict."""
        return json.loads(self.config) if self.config else {}


class SqliteArticle(SqliteBase):
    """Simplified Article model for testing with SQLite."""

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    topic: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # Enrichment fields
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_ai_related: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    enriched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


@pytest.fixture(scope="session")
def engine():
    """Create test database engine."""
    # Use SQLite for testing with simplified models
    engine = create_engine("sqlite:///:memory:")
    SqliteBase.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """Create test database session."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    # Cleanup - truncate tables to ensure test isolation
    session.rollback()
    session.execute(delete(SqliteArticle))
    session.execute(delete(SqliteSource))
    session.commit()
    session.close()
