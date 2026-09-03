"""SQLAlchemy models for the AI Daily data platform."""

from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class Source(Base):
    """Sources of content (newsletters, GitHub, crawlers)."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    articles: Mapped[list["Article"]] = relationship(
        "Article", back_populates="source", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("idx_sources_type", "type"),)


class Article(Base):
    """Core content store for articles."""

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
    )
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
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    # 768 dimensions for Google text-embedding-004
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Enrichment fields
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_ai_related: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    enriched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("articles.id"), nullable=True
    )

    source: Mapped["Source"] = relationship("Source", back_populates="articles")

    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_source_external"),
        Index("idx_articles_published", "published_at"),
        Index("idx_articles_topic", "topic"),
        Index("idx_articles_content_hash", "content_hash"),
        Index("idx_articles_source", "source_id"),
        Index("idx_articles_enriched_at", "enriched_at"),
        Index("idx_articles_is_duplicate", "is_duplicate"),
        Index("idx_articles_category", "category"),
    )


class DailySummary(Base):
    """Cached daily summaries."""

    __tablename__ = "daily_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), unique=True, nullable=False)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_facts: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    article_ids: Mapped[list[int] | None] = mapped_column(ARRAY(Integer), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class LeaderboardSnapshot(Base):
    """Point-in-time capture of an external model leaderboard.

    `rows` holds normalized entries [{name, rank?, metrics?}]; `content_hash`
    is over the ordered model names so an unchanged board stores nothing new.
    """

    __tablename__ = "leaderboard_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    board: Mapped[str] = mapped_column(String(100), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    rows: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (Index("idx_leaderboard_board_captured", "board", "captured_at"),)


class JobRun(Base):
    """Job execution tracking for observability."""

    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_name: Mapped[str] = mapped_column(String(100), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("idx_job_runs_name_started", "job_name", "started_at"),)
