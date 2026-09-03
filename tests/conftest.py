"""Pytest configuration and fixtures."""

import json
from datetime import UTC, datetime

import pytest
from sqlalchemy import Boolean, DateTime, Integer, String, Text, create_engine, delete
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


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
    config: Mapped[str | None] = mapped_column(Text, nullable=True)  # Store JSON as text
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

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
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    topic: Mapped[str | None] = mapped_column(String(100), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Enrichment fields
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_ai_related: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


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
