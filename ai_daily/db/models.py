"""SQLAlchemy models for the AI Daily data platform."""

from datetime import datetime
from typing import List, Optional

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
    config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    articles: Mapped[List["Article"]] = relationship("Article", back_populates="source", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_sources_type", "type"),
    )


class Article(Base):
    """Core content store for articles."""

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    topic: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tags: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), nullable=True)
    # 768 dimensions for Google text-embedding-004
    embedding: Mapped[Optional[List[float]]] = mapped_column(Vector(768), nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    source: Mapped["Source"] = relationship("Source", back_populates="articles")

    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_source_external"),
        Index("idx_articles_published", "published_at"),
        Index("idx_articles_topic", "topic"),
        Index("idx_articles_content_hash", "content_hash"),
        Index("idx_articles_source", "source_id"),
    )


class DailySummary(Base):
    """Cached daily summaries."""

    __tablename__ = "daily_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[datetime] = mapped_column(DateTime, unique=True, nullable=False)
    summary_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    key_facts: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    article_ids: Mapped[Optional[List[int]]] = mapped_column(ARRAY(Integer), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class JobRun(Base):
    """Job execution tracking for observability."""

    __tablename__ = "job_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_name: Mapped[str] = mapped_column(String(100), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    metrics: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_job_runs_name_started", "job_name", "started_at"),
    )
