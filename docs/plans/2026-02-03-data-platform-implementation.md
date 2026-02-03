# Data Platform Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform the AI Daily Summary project from a file-based newsletter processor into a multi-layered data platform with PostgreSQL storage, ETL pipelines, and multiple business outputs.

**Architecture:** Three-layer architecture: Data Layer (PostgreSQL + pgvector), ETL Layer (extractors + transformers + pipeline), Business Layer (newsletter, TTS, API, search). Each layer is independent and communicates through the database.

**Tech Stack:** Python 3.12+, PostgreSQL 16 + pgvector, SQLAlchemy 2.0, Alembic, FastAPI, Pocket TTS, OpenAI API, Click (CLI)

---

## Phase 1: Project Scaffolding

### Task 1: Create New Package Structure

**Files:**
- Create: `ai_daily/__init__.py`
- Create: `ai_daily/config.py`
- Modify: `pyproject.toml`

**Step 1: Create the ai_daily package directory**

```bash
mkdir -p ai_daily/db ai_daily/etl/extractors ai_daily/etl/transformers ai_daily/outputs ai_daily/api ai_daily/search
```

**Step 2: Create package init files**

Create `ai_daily/__init__.py`:
```python
"""AI Daily Summary - A data platform for AI news aggregation."""

__version__ = "0.2.0"
```

Create `ai_daily/db/__init__.py`:
```python
"""Database models and connection management."""
```

Create `ai_daily/etl/__init__.py`:
```python
"""ETL pipeline components."""
```

Create `ai_daily/etl/extractors/__init__.py`:
```python
"""Data extractors for various sources."""
```

Create `ai_daily/etl/transformers/__init__.py`:
```python
"""Data transformers for processing raw content."""
```

Create `ai_daily/outputs/__init__.py`:
```python
"""Output generators (newsletter, TTS, etc.)."""
```

Create `ai_daily/api/__init__.py`:
```python
"""API server components."""
```

Create `ai_daily/search/__init__.py`:
```python
"""Search functionality."""
```

**Step 3: Create config module**

Create `ai_daily/config.py`:
```python
"""Configuration management for AI Daily Summary."""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv

load_dotenv()


@dataclass
class DatabaseConfig:
    """Database configuration."""

    host: str = field(default_factory=lambda: os.getenv("DB_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("DB_PORT", "5432")))
    name: str = field(default_factory=lambda: os.getenv("DB_NAME", "ai_daily"))
    user: str = field(default_factory=lambda: os.getenv("DB_USER", "postgres"))
    password: str = field(default_factory=lambda: os.getenv("DB_PASSWORD", ""))

    @property
    def url(self) -> str:
        """Generate SQLAlchemy database URL."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

    @property
    def async_url(self) -> str:
        """Generate async SQLAlchemy database URL."""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


@dataclass
class LLMConfig:
    """LLM provider configuration."""

    provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "openai"))
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "gpt-4o-mini"))
    embedding_model: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"))
    ollama_base_url: str = field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"))


@dataclass
class GmailConfig:
    """Gmail API configuration."""

    client_id: str = field(default_factory=lambda: os.getenv("GOOGLE_CLIENT_ID", ""))
    client_secret: str = field(default_factory=lambda: os.getenv("GOOGLE_CLIENT_SECRET", ""))
    project_id: str = field(default_factory=lambda: os.getenv("GOOGLE_PROJECT_ID", ""))
    scopes: List[str] = field(default_factory=lambda: [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
    ])


@dataclass
class Config:
    """Main configuration container."""

    # Sub-configs
    db: DatabaseConfig = field(default_factory=DatabaseConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    gmail: GmailConfig = field(default_factory=GmailConfig)

    # Paths
    base_dir: Path = field(default_factory=lambda: Path(__file__).parent.parent)
    data_dir: Path = field(default_factory=lambda: Path("data"))
    logs_dir: Path = field(default_factory=lambda: Path("logs"))
    templates_dir: Path = field(default_factory=lambda: Path("email_templates"))
    config_file: Path = field(default_factory=lambda: Path("config.json"))

    # Newsletter
    recipients: List[str] = field(default_factory=lambda: [
        r.strip() for r in os.getenv("NEWSLETTER_RECIPIENTS", "").split(",") if r.strip()
    ])

    def __post_init__(self):
        """Ensure directories exist."""
        self.data_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)


# Global config instance
config = Config()
```

**Step 4: Update pyproject.toml**

Modify `pyproject.toml` to add new dependencies and update package structure:
```toml
[project]
name = "ai-daily-summary"
version = "0.2.0"
description = "AI news aggregation data platform"
readme = "README.md"
requires-python = ">=3.12"
authors = [
    { name = "Alexis Balayre", email = "60859013+AlexisBal@users.noreply.github.com" }
]
dependencies = [
    # Existing
    "python-dotenv>=1.0.1",
    "google-api-python-client>=2.159.0",
    "google-auth-httplib2>=0.2.0",
    "google-auth-oauthlib>=1.2.1",
    "openai>=1.60.2",
    "aiohttp>=3.11.12",
    "requests>=2.32.3",
    "beautifulsoup4>=4.13.3",
    # New - Database
    "sqlalchemy[asyncio]>=2.0.0",
    "asyncpg>=0.29.0",
    "psycopg2-binary>=2.9.9",
    "alembic>=1.13.0",
    "pgvector>=0.2.5",
    # New - API
    "fastapi>=0.109.0",
    "uvicorn>=0.27.0",
    # New - CLI
    "click>=8.1.0",
    "rich>=13.7.0",
    # New - TTS
    "pocket-tts>=0.1.0",
    "scipy>=1.12.0",
]

[project.scripts]
ai-daily = "ai_daily.cli:main"
scrape-github = "lib.github_scraper:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["ai_daily", "lib"]
```

**Step 5: Install new dependencies**

Run: `uv sync`
Expected: All dependencies install successfully

**Step 6: Verify package structure**

Run: `ls -la ai_daily/`
Expected: All directories and __init__.py files present

**Step 7: Commit**

```bash
git add ai_daily/ pyproject.toml
git commit -m "feat: scaffold new ai_daily package structure

- Create multi-layer package structure (db, etl, outputs, api, search)
- Add config module with dataclass-based configuration
- Update pyproject.toml with new dependencies (SQLAlchemy, FastAPI, etc.)
- Set up CLI entry point"
```

---

### Task 2: Set Up Database Models

**Files:**
- Create: `ai_daily/db/models.py`
- Create: `ai_daily/db/connection.py`

**Step 1: Create SQLAlchemy models**

Create `ai_daily/db/models.py`:
```python
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
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'newsletter', 'github', 'crawler'
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    articles: Mapped[List["Article"]] = relationship("Article", back_populates="source")


class Article(Base):
    """Core content store for articles."""

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(Integer, ForeignKey("sources.id"))
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Content
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Timestamps
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Categorization
    topic: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tags: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), nullable=True)

    # Vector search
    embedding: Mapped[Optional[List[float]]] = mapped_column(Vector(1536), nullable=True)

    # Deduplication
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Relationships
    source: Mapped["Source"] = relationship("Source", back_populates="articles")

    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_source_external"),
        Index("idx_articles_published", "published_at"),
        Index("idx_articles_topic", "topic"),
        Index("idx_articles_content_hash", "content_hash"),
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
    status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # 'running', 'success', 'failed'
    metrics: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_job_runs_name_started", "job_name", "started_at"),
    )
```

**Step 2: Create database connection module**

Create `ai_daily/db/connection.py`:
```python
"""Database connection and session management."""

from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from ai_daily.config import config
from ai_daily.db.models import Base


# Sync engine and session
engine = create_engine(config.db.url, echo=False)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

# Async engine and session
async_engine = create_async_engine(config.db.async_url, echo=False)
AsyncSessionLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False)


def init_db() -> None:
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


async def init_db_async() -> None:
    """Initialize database tables asynchronously."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Get a synchronous database session."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an asynchronous database session."""
    session = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
```

**Step 3: Update db __init__.py to export models**

Update `ai_daily/db/__init__.py`:
```python
"""Database models and connection management."""

from ai_daily.db.models import Article, Base, DailySummary, JobRun, Source
from ai_daily.db.connection import (
    get_session,
    get_async_session,
    init_db,
    init_db_async,
)

__all__ = [
    "Article",
    "Base",
    "DailySummary",
    "JobRun",
    "Source",
    "get_session",
    "get_async_session",
    "init_db",
    "init_db_async",
]
```

**Step 4: Verify models compile**

Run: `.venv/bin/python -c "from ai_daily.db import Article, Source, JobRun, DailySummary; print('Models OK')"`
Expected: "Models OK"

**Step 5: Commit**

```bash
git add ai_daily/db/
git commit -m "feat(db): add SQLAlchemy models for data platform

- Source: newsletter, github, crawler sources with JSONB config
- Article: core content with pgvector embedding support
- DailySummary: cached daily summaries
- JobRun: observability tracking
- Add sync and async session management"
```

---

### Task 3: Set Up Alembic Migrations

**Files:**
- Create: `alembic.ini`
- Create: `ai_daily/db/migrations/env.py`
- Create: `ai_daily/db/migrations/script.py.mako`
- Create: `ai_daily/db/migrations/versions/` (directory)

**Step 1: Initialize alembic**

Run: `.venv/bin/alembic init ai_daily/db/migrations`
Expected: Creates migrations directory structure

**Step 2: Configure alembic.ini**

Edit `alembic.ini` (created by init), update the sqlalchemy.url line:
```ini
# Replace the sqlalchemy.url line with:
sqlalchemy.url = postgresql://%(DB_USER)s:%(DB_PASSWORD)s@%(DB_HOST)s:%(DB_PORT)s/%(DB_NAME)s
```

**Step 3: Update migrations/env.py**

Replace `ai_daily/db/migrations/env.py` with:
```python
"""Alembic environment configuration."""

import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

# Load environment variables
load_dotenv()

# Import models for autogenerate support
from ai_daily.db.models import Base

# Alembic Config object
config = context.config

# Set database URL from environment
config.set_main_option("DB_USER", os.getenv("DB_USER", "postgres"))
config.set_main_option("DB_PASSWORD", os.getenv("DB_PASSWORD", ""))
config.set_main_option("DB_HOST", os.getenv("DB_HOST", "localhost"))
config.set_main_option("DB_PORT", os.getenv("DB_PORT", "5432"))
config.set_main_option("DB_NAME", os.getenv("DB_NAME", "ai_daily"))

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Model metadata for autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

**Step 4: Create initial migration**

Run: `.venv/bin/alembic revision --autogenerate -m "initial schema"`
Expected: Creates migration file in versions/

**Step 5: Commit**

```bash
git add alembic.ini ai_daily/db/migrations/
git commit -m "feat(db): set up Alembic migrations

- Configure alembic.ini with env var substitution
- Set up env.py with model imports for autogenerate
- Create initial migration for all tables"
```

---

## Phase 2: ETL Layer - Extractors

### Task 4: Create Base Extractor Interface

**Files:**
- Create: `ai_daily/etl/extractors/base.py`
- Create: `ai_daily/etl/types.py`

**Step 1: Create shared types**

Create `ai_daily/etl/types.py`:
```python
"""Shared types for ETL pipeline."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class RawContent:
    """Raw content extracted from a source before transformation."""

    external_id: str
    title: str
    content: str
    url: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    source_name: str = ""
    metadata: dict = field(default_factory=dict)
```

**Step 2: Create base extractor**

Create `ai_daily/etl/extractors/base.py`:
```python
"""Base extractor interface for all data sources."""

from abc import ABC, abstractmethod
from typing import List

from ai_daily.db.models import Source
from ai_daily.etl.types import RawContent


class BaseExtractor(ABC):
    """Abstract base class for all extractors."""

    @abstractmethod
    async def extract(self, source: Source) -> List[RawContent]:
        """
        Extract raw content from the source.

        Args:
            source: The Source model instance with configuration.

        Returns:
            List of RawContent items extracted from the source.
        """
        pass

    @abstractmethod
    def get_external_id(self, item: RawContent) -> str:
        """
        Generate a unique external ID for deduplication.

        Args:
            item: The raw content item.

        Returns:
            A unique string identifier for this content.
        """
        pass

    def supports_source_type(self, source_type: str) -> bool:
        """Check if this extractor supports the given source type."""
        return source_type in self.supported_types

    @property
    @abstractmethod
    def supported_types(self) -> List[str]:
        """List of source types this extractor supports."""
        pass
```

**Step 3: Update extractors __init__.py**

Update `ai_daily/etl/extractors/__init__.py`:
```python
"""Data extractors for various sources."""

from ai_daily.etl.extractors.base import BaseExtractor

__all__ = ["BaseExtractor"]
```

**Step 4: Verify imports**

Run: `.venv/bin/python -c "from ai_daily.etl.extractors import BaseExtractor; from ai_daily.etl.types import RawContent; print('OK')"`
Expected: "OK"

**Step 5: Commit**

```bash
git add ai_daily/etl/
git commit -m "feat(etl): add base extractor interface and RawContent type

- BaseExtractor ABC with extract() and get_external_id() methods
- RawContent dataclass for normalized extracted data
- Support for source type checking"
```

---

### Task 5: Implement Gmail Extractor

**Files:**
- Create: `ai_daily/etl/extractors/gmail.py`

**Step 1: Create Gmail extractor**

Create `ai_daily/etl/extractors/gmail.py`:
```python
"""Gmail newsletter extractor."""

import base64
import hashlib
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Set

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from ai_daily.config import config
from ai_daily.db.models import Source
from ai_daily.etl.extractors.base import BaseExtractor
from ai_daily.etl.types import RawContent


class GmailExtractor(BaseExtractor):
    """Extract newsletter content from Gmail."""

    def __init__(self):
        self.service = self._authenticate()
        self._processed_ids: Set[str] = set()

    @property
    def supported_types(self) -> List[str]:
        return ["newsletter"]

    def _authenticate(self):
        """Authenticate with Gmail API using OAuth 2.0."""
        creds = None
        token_path = Path("token.json")

        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), config.gmail.scopes)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_config(
                    {
                        "web": {
                            "client_id": config.gmail.client_id,
                            "project_id": config.gmail.project_id,
                            "auth_uri": os.getenv("GOOGLE_AUTH_URI"),
                            "token_uri": os.getenv("GOOGLE_TOKEN_URI"),
                            "auth_provider_x509_cert_url": os.getenv("GOOGLE_AUTH_PROVIDER_X509_CERT_URL"),
                            "client_secret": config.gmail.client_secret,
                            "redirect_uris": ["http://localhost:56450/"],
                        }
                    },
                    config.gmail.scopes,
                )
                creds = flow.run_local_server(port=56450)

            with open(token_path, "w") as token:
                token.write(creds.to_json())

        return build("gmail", "v1", credentials=creds)

    def _load_whitelist(self, source: Source) -> Set[str]:
        """Load whitelist from source config or config file."""
        # Try source config first
        if source.config and "whitelist" in source.config:
            return set(source.config["whitelist"])

        # Fall back to config.json
        if config.config_file.exists():
            with open(config.config_file) as f:
                data = json.load(f)
                return set(data.get("whitelist", []))

        return set()

    def _parse_email_date(self, date_str: str) -> Optional[datetime]:
        """Parse email date string."""
        date_str = date_str.replace(" (UTC)", "")
        try:
            return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
        except ValueError:
            try:
                return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S")
            except ValueError:
                return None

    def _extract_email_body(self, payload: dict) -> str:
        """Extract email body from Gmail payload."""
        if "parts" in payload:
            for part in payload["parts"]:
                if part.get("mimeType") == "text/plain":
                    data = part.get("body", {}).get("data", "")
                    if data:
                        return base64.urlsafe_b64decode(data).decode("utf-8")
        else:
            data = payload.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8")
        return ""

    def _extract_sender_email(self, sender: str) -> str:
        """Extract email address from sender string."""
        match = re.search(r"<(.+?)>", sender)
        return match.group(1) if match else sender.strip()

    async def extract(self, source: Source) -> List[RawContent]:
        """Extract newsletters from Gmail."""
        whitelist = self._load_whitelist(source)
        days_back = source.config.get("days_back", 2) if source.config else 2

        # Search for recent emails
        date_threshold = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y/%m/%d")
        search_query = f"after:{date_threshold}"

        results = self.service.users().messages().list(userId="me", q=search_query).execute()
        messages = results.get("messages", [])

        if not messages:
            return []

        raw_contents = []

        for message in messages:
            msg_id = message["id"]

            # Skip already processed
            if msg_id in self._processed_ids:
                continue

            # Fetch full message
            msg = self.service.users().messages().get(userId="me", id=msg_id, format="full").execute()
            payload = msg["payload"]
            headers = {h["name"]: h["value"] for h in payload.get("headers", [])}

            # Check whitelist
            sender = headers.get("From", "")
            sender_email = self._extract_sender_email(sender)
            if sender_email not in whitelist:
                continue

            # Extract content
            body = self._extract_email_body(payload)
            if not body:
                continue

            published_at = self._parse_email_date(headers.get("Date", ""))

            raw_content = RawContent(
                external_id=msg_id,
                title=headers.get("Subject", ""),
                content=body,
                author=sender,
                published_at=published_at,
                source_name=sender_email,
                metadata={
                    "gmail_id": msg_id,
                    "snippet": msg.get("snippet", ""),
                }
            )

            raw_contents.append(raw_content)
            self._processed_ids.add(msg_id)

        return raw_contents

    def get_external_id(self, item: RawContent) -> str:
        """Use Gmail message ID as external ID."""
        return item.external_id
```

**Step 2: Update extractors __init__.py**

Update `ai_daily/etl/extractors/__init__.py`:
```python
"""Data extractors for various sources."""

from ai_daily.etl.extractors.base import BaseExtractor
from ai_daily.etl.extractors.gmail import GmailExtractor

__all__ = ["BaseExtractor", "GmailExtractor"]
```

**Step 3: Verify extractor imports**

Run: `.venv/bin/python -c "from ai_daily.etl.extractors import GmailExtractor; print('OK')"`
Expected: "OK"

**Step 4: Commit**

```bash
git add ai_daily/etl/extractors/gmail.py ai_daily/etl/extractors/__init__.py
git commit -m "feat(etl): implement Gmail newsletter extractor

- OAuth 2.0 authentication with token refresh
- Whitelist filtering from source config or config.json
- Email body extraction with MIME handling
- Date parsing with timezone support"
```

---

### Task 6: Implement GitHub Extractor

**Files:**
- Create: `ai_daily/etl/extractors/github.py`

**Step 1: Create GitHub extractor**

Create `ai_daily/etl/extractors/github.py`:
```python
"""GitHub trending repositories extractor."""

import hashlib
import os
from dataclasses import asdict
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

        # Get config options
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
```

**Step 2: Update extractors __init__.py**

Update `ai_daily/etl/extractors/__init__.py`:
```python
"""Data extractors for various sources."""

from ai_daily.etl.extractors.base import BaseExtractor
from ai_daily.etl.extractors.gmail import GmailExtractor
from ai_daily.etl.extractors.github import GitHubExtractor

__all__ = ["BaseExtractor", "GmailExtractor", "GitHubExtractor"]
```

**Step 3: Verify**

Run: `.venv/bin/python -c "from ai_daily.etl.extractors import GitHubExtractor; print('OK')"`
Expected: "OK"

**Step 4: Commit**

```bash
git add ai_daily/etl/extractors/github.py ai_daily/etl/extractors/__init__.py
git commit -m "feat(etl): implement GitHub trending/explore extractor

- Trending page scraping with stars, forks, language
- Explore page scraping
- Fallback description fetching from repo page
- Configurable via source config"
```

---

### Task 7: Implement Web Crawler Extractor

**Files:**
- Create: `ai_daily/etl/extractors/crawler.py`

**Step 1: Create crawler extractor**

Create `ai_daily/etl/extractors/crawler.py`:
```python
"""Web crawler extractor for monitoring websites."""

import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

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
        """Fetch full article content from URL."""
        if not content_selector:
            return ""

        soup = self._fetch_page(url)
        if not soup:
            return ""

        content_elem = soup.select_one(content_selector)
        if content_elem:
            return content_elem.get_text(strip=True)
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
                    # Handle relative URLs
                    from urllib.parse import urljoin
                    link = urljoin(url, link)

                description = self._extract_attribute(item, description_selector)
                author = self._extract_attribute(item, author_selector)
                date_str = self._extract_attribute(item, date_selector)

                # Determine content
                if content_mode == "fetch_full" and link:
                    content = self._fetch_full_content(link, content_selector)
                    if not content:
                        content = description
                else:
                    content = description

                if not content:
                    content = title

                # Generate external ID from URL or title
                external_id = hashlib.md5((link or title).encode()).hexdigest()

                raw_contents.append(RawContent(
                    external_id=external_id,
                    title=title,
                    content=content,
                    url=link,
                    author=author if author else None,
                    published_at=datetime.utcnow(),  # Could parse date_str if needed
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
```

**Step 2: Update extractors __init__.py**

Update `ai_daily/etl/extractors/__init__.py`:
```python
"""Data extractors for various sources."""

from ai_daily.etl.extractors.base import BaseExtractor
from ai_daily.etl.extractors.crawler import CrawlerExtractor
from ai_daily.etl.extractors.github import GitHubExtractor
from ai_daily.etl.extractors.gmail import GmailExtractor

__all__ = [
    "BaseExtractor",
    "CrawlerExtractor",
    "GitHubExtractor",
    "GmailExtractor",
]
```

**Step 3: Verify**

Run: `.venv/bin/python -c "from ai_daily.etl.extractors import CrawlerExtractor; print('OK')"`
Expected: "OK"

**Step 4: Commit**

```bash
git add ai_daily/etl/extractors/crawler.py ai_daily/etl/extractors/__init__.py
git commit -m "feat(etl): implement configurable web crawler extractor

- CSS selector-based content extraction
- Attribute extraction with @attr syntax
- Support for summary_only and fetch_full content modes
- Relative URL handling"
```

---

## Phase 3: ETL Layer - Transformers

### Task 8: Implement LLM Parser Transformer

**Files:**
- Create: `ai_daily/etl/transformers/llm_parser.py`

**Step 1: Create LLM parser**

Create `ai_daily/etl/transformers/llm_parser.py`:
```python
"""LLM-based content parser for extracting structured articles."""

import json
from typing import Dict, List, Optional

from openai import AsyncOpenAI

from ai_daily.config import config
from ai_daily.etl.types import RawContent


class LLMParser:
    """Parse raw content into structured articles using LLM."""

    SYSTEM_PROMPT = """You are an expert at extracting structured data from newsletter content.

Extract articles that match these topics:
- AI Research and Advances
- AI Products, Tools, and Repositories
- Data Science Techniques and Tips
- Industry News and Trends

For each article, identify:
- title: Clear, descriptive title
- content: Main content summary (2-3 sentences)
- topic: One of the categories above
- url: URL if mentioned

Output valid JSON:
{
    "articles": [
        {"title": "...", "content": "...", "topic": "...", "url": "..."}
    ]
}"""

    def __init__(self):
        if config.llm.provider == "ollama":
            self.client = AsyncOpenAI(
                base_url=config.llm.ollama_base_url,
                api_key="ollama"
            )
        else:
            self.client = AsyncOpenAI()
        self.model = config.llm.model

    async def parse(self, raw_content: RawContent) -> List[Dict]:
        """Parse raw content into structured articles.

        Args:
            raw_content: The raw content to parse.

        Returns:
            List of article dictionaries with title, content, topic, url.
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": f"Content:\n{raw_content.content[:8000]}"}
                ],
                response_format={"type": "json_object"},
            )

            result = json.loads(response.choices[0].message.content)
            articles = result.get("articles", [])

            # Add source info to each article
            for article in articles:
                article["source_name"] = raw_content.source_name
                article["external_id"] = raw_content.external_id
                if not article.get("url"):
                    article["url"] = raw_content.url

            return articles
        except Exception:
            # If parsing fails, return the raw content as a single article
            return [{
                "title": raw_content.title,
                "content": raw_content.content[:1000],
                "topic": "Industry News and Trends",
                "url": raw_content.url,
                "source_name": raw_content.source_name,
                "external_id": raw_content.external_id,
            }]
```

**Step 2: Update transformers __init__.py**

Update `ai_daily/etl/transformers/__init__.py`:
```python
"""Data transformers for processing raw content."""

from ai_daily.etl.transformers.llm_parser import LLMParser

__all__ = ["LLMParser"]
```

**Step 3: Verify**

Run: `.venv/bin/python -c "from ai_daily.etl.transformers import LLMParser; print('OK')"`
Expected: "OK"

**Step 4: Commit**

```bash
git add ai_daily/etl/transformers/
git commit -m "feat(etl): implement LLM parser transformer

- OpenAI/Ollama support based on config
- JSON structured output for articles
- Topic categorization
- Fallback handling for parse failures"
```

---

### Task 9: Implement Embedder Transformer

**Files:**
- Create: `ai_daily/etl/transformers/embedder.py`

**Step 1: Create embedder**

Create `ai_daily/etl/transformers/embedder.py`:
```python
"""Generate vector embeddings for articles."""

from typing import List

from openai import AsyncOpenAI

from ai_daily.config import config


class Embedder:
    """Generate vector embeddings using OpenAI or Ollama."""

    def __init__(self):
        if config.llm.provider == "ollama":
            self.client = AsyncOpenAI(
                base_url=config.llm.ollama_base_url,
                api_key="ollama"
            )
            self.model = "nomic-embed-text"  # Ollama embedding model
        else:
            self.client = AsyncOpenAI()
            self.model = config.llm.embedding_model

    async def embed(self, text: str) -> List[float]:
        """Generate embedding for text.

        Args:
            text: Text to embed.

        Returns:
            Vector embedding as list of floats.
        """
        # Truncate to avoid token limits
        text = text[:8000]

        response = await self.client.embeddings.create(
            model=self.model,
            input=text,
        )

        return response.data[0].embedding

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed.

        Returns:
            List of vector embeddings.
        """
        # Truncate each text
        texts = [t[:8000] for t in texts]

        response = await self.client.embeddings.create(
            model=self.model,
            input=texts,
        )

        return [d.embedding for d in response.data]
```

**Step 2: Update transformers __init__.py**

Update `ai_daily/etl/transformers/__init__.py`:
```python
"""Data transformers for processing raw content."""

from ai_daily.etl.transformers.embedder import Embedder
from ai_daily.etl.transformers.llm_parser import LLMParser

__all__ = ["Embedder", "LLMParser"]
```

**Step 3: Verify**

Run: `.venv/bin/python -c "from ai_daily.etl.transformers import Embedder; print('OK')"`
Expected: "OK"

**Step 4: Commit**

```bash
git add ai_daily/etl/transformers/
git commit -m "feat(etl): implement embedder transformer

- OpenAI text-embedding-3-small by default
- Ollama nomic-embed-text support
- Single and batch embedding methods
- Text truncation for token limits"
```

---

### Task 10: Implement Deduplicator

**Files:**
- Create: `ai_daily/etl/transformers/deduplicator.py`

**Step 1: Create deduplicator**

Create `ai_daily/etl/transformers/deduplicator.py`:
```python
"""Content deduplication using hash and semantic similarity."""

import hashlib
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_daily.db.models import Article


def compute_content_hash(title: str, content: str) -> str:
    """Compute MD5 hash of title + content prefix."""
    text = f"{title}{content[:200]}"
    return hashlib.md5(text.encode()).hexdigest()


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0

    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)


class Deduplicator:
    """Check for duplicate content using hash and embedding similarity."""

    SIMILARITY_THRESHOLD = 0.92

    def __init__(self, session: Session):
        self.session = session

    def is_duplicate_by_hash(self, content_hash: str) -> bool:
        """Check if content hash already exists."""
        stmt = select(Article.id).where(Article.content_hash == content_hash).limit(1)
        result = self.session.execute(stmt).first()
        return result is not None

    def is_duplicate_by_external_id(self, source_id: int, external_id: str) -> bool:
        """Check if external ID already exists for this source."""
        stmt = select(Article.id).where(
            Article.source_id == source_id,
            Article.external_id == external_id
        ).limit(1)
        result = self.session.execute(stmt).first()
        return result is not None

    def find_similar_by_embedding(
        self,
        embedding: List[float],
        limit: int = 5
    ) -> List[Tuple[int, float]]:
        """Find similar articles by embedding.

        Note: For production, use pgvector's built-in similarity search.
        This is a fallback implementation.

        Returns:
            List of (article_id, similarity_score) tuples.
        """
        # For now, fetch recent articles and compare manually
        # In production, use: Article.embedding.cosine_distance(embedding)
        stmt = select(Article).where(Article.embedding.isnot(None)).limit(100)
        articles = self.session.execute(stmt).scalars().all()

        similarities = []
        for article in articles:
            if article.embedding:
                sim = cosine_similarity(embedding, list(article.embedding))
                if sim >= self.SIMILARITY_THRESHOLD:
                    similarities.append((article.id, sim))

        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:limit]

    def is_duplicate(
        self,
        source_id: int,
        external_id: str,
        content_hash: str,
        embedding: Optional[List[float]] = None
    ) -> Tuple[bool, Optional[int]]:
        """Check if content is duplicate.

        Args:
            source_id: Source ID.
            external_id: External ID from source.
            content_hash: MD5 hash of content.
            embedding: Optional embedding for semantic dedup.

        Returns:
            Tuple of (is_duplicate, related_article_id).
        """
        # Check external ID first (fastest)
        if self.is_duplicate_by_external_id(source_id, external_id):
            return True, None

        # Check content hash
        if self.is_duplicate_by_hash(content_hash):
            return True, None

        # Check semantic similarity if embedding provided
        if embedding:
            similar = self.find_similar_by_embedding(embedding, limit=1)
            if similar:
                return True, similar[0][0]

        return False, None
```

**Step 2: Update transformers __init__.py**

Update `ai_daily/etl/transformers/__init__.py`:
```python
"""Data transformers for processing raw content."""

from ai_daily.etl.transformers.deduplicator import Deduplicator, compute_content_hash
from ai_daily.etl.transformers.embedder import Embedder
from ai_daily.etl.transformers.llm_parser import LLMParser

__all__ = ["Deduplicator", "Embedder", "LLMParser", "compute_content_hash"]
```

**Step 3: Verify**

Run: `.venv/bin/python -c "from ai_daily.etl.transformers import Deduplicator, compute_content_hash; print('OK')"`
Expected: "OK"

**Step 4: Commit**

```bash
git add ai_daily/etl/transformers/
git commit -m "feat(etl): implement deduplication transformer

- Hash-based exact deduplication
- External ID deduplication per source
- Semantic similarity with cosine distance
- Configurable similarity threshold (0.92)"
```

---

### Task 11: Implement ETL Pipeline Orchestrator

**Files:**
- Create: `ai_daily/etl/pipeline.py`

**Step 1: Create pipeline orchestrator**

Create `ai_daily/etl/pipeline.py`:
```python
"""ETL Pipeline orchestrator."""

import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, List, Optional, Type

from sqlalchemy.orm import Session

from ai_daily.db import Article, JobRun, Source, get_session
from ai_daily.etl.extractors import BaseExtractor, CrawlerExtractor, GitHubExtractor, GmailExtractor
from ai_daily.etl.transformers import Deduplicator, Embedder, LLMParser, compute_content_hash
from ai_daily.etl.types import RawContent

logger = logging.getLogger(__name__)


# Registry of extractors by source type
EXTRACTORS: Dict[str, Type[BaseExtractor]] = {
    "newsletter": GmailExtractor,
    "github": GitHubExtractor,
    "crawler": CrawlerExtractor,
}


@contextmanager
def track_job(session: Session, job_name: str):
    """Context manager for tracking job execution."""
    job = JobRun(job_name=job_name, status="running")
    session.add(job)
    session.commit()

    metrics = {"articles_processed": 0, "articles_created": 0, "duplicates_skipped": 0}

    try:
        yield job, metrics
        job.status = "success"
        job.metrics = metrics
    except Exception as e:
        job.status = "failed"
        job.error_message = str(e)
        job.metrics = metrics
        raise
    finally:
        job.finished_at = datetime.utcnow()
        session.commit()


class ETLPipeline:
    """Main ETL pipeline orchestrator."""

    def __init__(self):
        self.extractors: Dict[str, BaseExtractor] = {}
        self.llm_parser = LLMParser()
        self.embedder = Embedder()

    def _get_extractor(self, source_type: str) -> BaseExtractor:
        """Get or create extractor for source type."""
        if source_type not in self.extractors:
            extractor_class = EXTRACTORS.get(source_type)
            if not extractor_class:
                raise ValueError(f"No extractor for source type: {source_type}")
            self.extractors[source_type] = extractor_class()
        return self.extractors[source_type]

    async def run_for_source(self, source: Source, session: Session) -> Dict:
        """Run ETL pipeline for a single source.

        Returns:
            Dict with processing metrics.
        """
        job_name = f"etl_{source.type}_{source.id}"

        with track_job(session, job_name) as (job, metrics):
            # Extract
            extractor = self._get_extractor(source.type)
            raw_contents = await extractor.extract(source)
            logger.info(f"Extracted {len(raw_contents)} items from {source.name}")

            deduplicator = Deduplicator(session)

            for raw in raw_contents:
                metrics["articles_processed"] += 1

                # Parse with LLM (for newsletters) or use as-is (for GitHub/crawlers)
                if source.type == "newsletter":
                    articles_data = await self.llm_parser.parse(raw)
                else:
                    articles_data = [{
                        "title": raw.title,
                        "content": raw.content,
                        "topic": "AI Products, Tools, and Repositories" if source.type == "github" else "Industry News and Trends",
                        "url": raw.url,
                        "source_name": raw.source_name,
                        "external_id": raw.external_id,
                    }]

                for article_data in articles_data:
                    # Compute hash
                    content_hash = compute_content_hash(
                        article_data["title"],
                        article_data["content"]
                    )

                    # Check duplicate
                    is_dup, related_id = deduplicator.is_duplicate(
                        source_id=source.id,
                        external_id=article_data.get("external_id", raw.external_id),
                        content_hash=content_hash,
                    )

                    if is_dup:
                        metrics["duplicates_skipped"] += 1
                        continue

                    # Generate embedding
                    embed_text = f"{article_data['title']} {article_data['content']}"
                    embedding = await self.embedder.embed(embed_text)

                    # Check semantic duplicate
                    is_dup, related_id = deduplicator.is_duplicate(
                        source_id=source.id,
                        external_id=article_data.get("external_id", raw.external_id),
                        content_hash=content_hash,
                        embedding=embedding,
                    )

                    if is_dup:
                        metrics["duplicates_skipped"] += 1
                        continue

                    # Create article
                    article = Article(
                        source_id=source.id,
                        external_id=article_data.get("external_id", raw.external_id),
                        title=article_data["title"],
                        content=article_data["content"],
                        url=article_data.get("url"),
                        author=raw.author,
                        published_at=raw.published_at,
                        topic=article_data.get("topic"),
                        embedding=embedding,
                        content_hash=content_hash,
                    )
                    session.add(article)
                    metrics["articles_created"] += 1

            session.commit()
            logger.info(f"Created {metrics['articles_created']} articles, skipped {metrics['duplicates_skipped']} duplicates")

        return metrics

    async def run_all(self, source_types: Optional[List[str]] = None) -> Dict:
        """Run ETL for all enabled sources.

        Args:
            source_types: Optional list of source types to run. If None, runs all.

        Returns:
            Dict with aggregated metrics.
        """
        total_metrics = {"articles_processed": 0, "articles_created": 0, "duplicates_skipped": 0}

        with get_session() as session:
            # Get enabled sources
            query = session.query(Source).filter(Source.enabled == True)
            if source_types:
                query = query.filter(Source.type.in_(source_types))

            sources = query.all()

            for source in sources:
                try:
                    metrics = await self.run_for_source(source, session)
                    for key in total_metrics:
                        total_metrics[key] += metrics.get(key, 0)
                except Exception as e:
                    logger.error(f"Error processing source {source.name}: {e}")

        return total_metrics
```

**Step 2: Update etl __init__.py**

Update `ai_daily/etl/__init__.py`:
```python
"""ETL pipeline components."""

from ai_daily.etl.pipeline import ETLPipeline
from ai_daily.etl.types import RawContent

__all__ = ["ETLPipeline", "RawContent"]
```

**Step 3: Verify**

Run: `.venv/bin/python -c "from ai_daily.etl import ETLPipeline; print('OK')"`
Expected: "OK"

**Step 4: Commit**

```bash
git add ai_daily/etl/
git commit -m "feat(etl): implement pipeline orchestrator

- Source-specific extractor selection
- LLM parsing for newsletters
- Embedding generation for all content
- Two-phase deduplication (hash + semantic)
- Job tracking with metrics
- Batch and per-source execution modes"
```

---

## Phase 4: CLI

### Task 12: Implement CLI

**Files:**
- Create: `ai_daily/cli.py`

**Step 1: Create CLI module**

Create `ai_daily/cli.py`:
```python
"""CLI entry point for AI Daily Summary."""

import asyncio
from datetime import datetime, timedelta

import click
from rich.console import Console
from rich.table import Table

from ai_daily.db import JobRun, Source, get_session, init_db

console = Console()


@click.group()
def main():
    """AI Daily Summary - Data platform for AI news aggregation."""
    pass


@main.command()
def init():
    """Initialize the database."""
    init_db()
    console.print("[green]Database initialized successfully![/green]")


@main.command()
@click.argument("job_type", type=click.Choice(["gmail", "github", "crawlers", "all"]))
def run(job_type: str):
    """Run ETL pipeline for specified source type."""
    from ai_daily.etl import ETLPipeline

    async def _run():
        pipeline = ETLPipeline()

        if job_type == "all":
            metrics = await pipeline.run_all()
        else:
            type_map = {"gmail": "newsletter", "github": "github", "crawlers": "crawler"}
            metrics = await pipeline.run_all(source_types=[type_map[job_type]])

        console.print(f"[green]ETL completed![/green]")
        console.print(f"  Processed: {metrics['articles_processed']}")
        console.print(f"  Created: {metrics['articles_created']}")
        console.print(f"  Duplicates: {metrics['duplicates_skipped']}")

    asyncio.run(_run())


@main.command()
def status():
    """Show recent job runs."""
    with get_session() as session:
        yesterday = datetime.utcnow() - timedelta(days=1)
        jobs = session.query(JobRun).filter(
            JobRun.started_at >= yesterday
        ).order_by(JobRun.started_at.desc()).limit(20).all()

        if not jobs:
            console.print("[yellow]No jobs in the last 24 hours[/yellow]")
            return

        table = Table(title="Job Runs (Last 24h)")
        table.add_column("Status", style="cyan")
        table.add_column("Job", style="magenta")
        table.add_column("Started", style="green")
        table.add_column("Duration")
        table.add_column("Metrics")

        for job in jobs:
            status_icon = "✓" if job.status == "success" else "✗" if job.status == "failed" else "⋯"
            status_color = "green" if job.status == "success" else "red" if job.status == "failed" else "yellow"

            duration = ""
            if job.finished_at and job.started_at:
                delta = job.finished_at - job.started_at
                duration = f"{delta.total_seconds():.1f}s"

            metrics_str = ""
            if job.metrics:
                if "articles_created" in job.metrics:
                    metrics_str = f"{job.metrics['articles_created']} articles"

            table.add_row(
                f"[{status_color}]{status_icon}[/{status_color}]",
                job.job_name,
                job.started_at.strftime("%H:%M"),
                duration,
                metrics_str,
            )

        console.print(table)


@main.command()
@click.argument("query")
def search(query: str):
    """Search articles by keyword."""
    from sqlalchemy import or_
    from ai_daily.db import Article

    with get_session() as session:
        articles = session.query(Article).filter(
            or_(
                Article.title.ilike(f"%{query}%"),
                Article.content.ilike(f"%{query}%"),
            )
        ).order_by(Article.published_at.desc()).limit(10).all()

        if not articles:
            console.print(f"[yellow]No articles found for '{query}'[/yellow]")
            return

        for article in articles:
            console.print(f"\n[bold cyan]{article.title}[/bold cyan]")
            console.print(f"[dim]{article.topic} | {article.published_at}[/dim]")
            console.print(article.content[:200] + "..." if len(article.content) > 200 else article.content)
            if article.url:
                console.print(f"[blue]{article.url}[/blue]")


@main.command()
def serve():
    """Start the API server."""
    import uvicorn
    uvicorn.run("ai_daily.api.server:app", host="0.0.0.0", port=8000, reload=True)


@main.group()
def source():
    """Manage sources."""
    pass


@source.command("list")
def source_list():
    """List all sources."""
    with get_session() as session:
        sources = session.query(Source).all()

        if not sources:
            console.print("[yellow]No sources configured[/yellow]")
            return

        table = Table(title="Sources")
        table.add_column("ID", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Name", style="green")
        table.add_column("Enabled")

        for src in sources:
            enabled = "✓" if src.enabled else "✗"
            table.add_row(str(src.id), src.type, src.name, enabled)

        console.print(table)


@source.command("add")
@click.argument("source_type", type=click.Choice(["newsletter", "github", "crawler"]))
@click.argument("name")
@click.option("--config", "-c", help="JSON config string")
def source_add(source_type: str, name: str, config: str = None):
    """Add a new source."""
    import json

    with get_session() as session:
        src = Source(
            type=source_type,
            name=name,
            config=json.loads(config) if config else None,
            enabled=True,
        )
        session.add(src)
        session.commit()
        console.print(f"[green]Added source: {name} (ID: {src.id})[/green]")


if __name__ == "__main__":
    main()
```

**Step 2: Verify CLI works**

Run: `.venv/bin/python -m ai_daily.cli --help`
Expected: Shows CLI help with all commands

**Step 3: Commit**

```bash
git add ai_daily/cli.py
git commit -m "feat: implement CLI with Rich output

Commands:
- init: Initialize database
- run: Run ETL pipeline (gmail/github/crawlers/all)
- status: Show recent job runs with table
- search: Basic keyword search
- serve: Start API server
- source list/add: Manage sources"
```

---

## Phase 5: Business Layer

### Task 13: Implement Summary Generator

**Files:**
- Create: `ai_daily/outputs/summary_generator.py`

**Step 1: Create summary generator**

Create `ai_daily/outputs/summary_generator.py`:
```python
"""Generate daily summaries from articles."""

import json
from datetime import date, datetime, timedelta
from typing import List, Optional

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_daily.config import config
from ai_daily.db import Article, DailySummary


class SummaryGenerator:
    """Generate daily summaries using LLM."""

    SYSTEM_PROMPT = """You are an expert AI news summarizer.

Given today's articles, create:
1. A concise summary (2-3 paragraphs) of the key developments
2. A list of the most important facts (5-10 bullet points)

Focus on:
- AI Research breakthroughs
- New tools and products
- Industry trends
- Notable data science techniques

Output valid JSON:
{
    "summary": "...",
    "key_facts": ["...", "..."]
}"""

    def __init__(self):
        if config.llm.provider == "ollama":
            self.client = AsyncOpenAI(
                base_url=config.llm.ollama_base_url,
                api_key="ollama"
            )
        else:
            self.client = AsyncOpenAI()
        self.model = config.llm.model

    def get_cached_summary(self, session: Session, target_date: date) -> Optional[DailySummary]:
        """Get cached summary for date if exists."""
        stmt = select(DailySummary).where(
            DailySummary.date == datetime.combine(target_date, datetime.min.time())
        )
        return session.execute(stmt).scalar_one_or_none()

    def get_articles_for_date(self, session: Session, target_date: date) -> List[Article]:
        """Get articles for a specific date."""
        start = datetime.combine(target_date, datetime.min.time())
        end = start + timedelta(days=1)

        stmt = select(Article).where(
            Article.ingested_at >= start,
            Article.ingested_at < end
        ).order_by(Article.ingested_at.desc())

        return list(session.execute(stmt).scalars().all())

    async def generate(self, session: Session, target_date: Optional[date] = None) -> DailySummary:
        """Generate summary for a date.

        Args:
            session: Database session.
            target_date: Date to summarize. Defaults to today.

        Returns:
            DailySummary model instance.
        """
        if target_date is None:
            target_date = date.today()

        # Check cache
        cached = self.get_cached_summary(session, target_date)
        if cached:
            return cached

        # Get articles
        articles = self.get_articles_for_date(session, target_date)

        if not articles:
            summary = DailySummary(
                date=datetime.combine(target_date, datetime.min.time()),
                summary_text="No articles for today.",
                key_facts=[],
                article_ids=[],
            )
            session.add(summary)
            session.commit()
            return summary

        # Prepare content
        articles_text = "\n\n".join(
            f"Title: {a.title}\nTopic: {a.topic}\nContent: {a.content[:500]}"
            for a in articles[:50]  # Limit to avoid token limits
        )

        # Generate summary
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": f"Articles for {target_date}:\n\n{articles_text}"}
            ],
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)

        # Create and save summary
        summary = DailySummary(
            date=datetime.combine(target_date, datetime.min.time()),
            summary_text=result.get("summary", ""),
            key_facts=result.get("key_facts", []),
            article_ids=[a.id for a in articles],
        )
        session.add(summary)
        session.commit()

        return summary
```

**Step 2: Update outputs __init__.py**

Update `ai_daily/outputs/__init__.py`:
```python
"""Output generators (newsletter, TTS, etc.)."""

from ai_daily.outputs.summary_generator import SummaryGenerator

__all__ = ["SummaryGenerator"]
```

**Step 3: Verify**

Run: `.venv/bin/python -c "from ai_daily.outputs import SummaryGenerator; print('OK')"`
Expected: "OK"

**Step 4: Commit**

```bash
git add ai_daily/outputs/
git commit -m "feat(outputs): implement summary generator

- LLM-based daily summary generation
- Caching in daily_summaries table
- Key facts extraction
- Article ID tracking"
```

---

### Task 14: Implement Newsletter Output

**Files:**
- Create: `ai_daily/outputs/newsletter.py`

**Step 1: Create newsletter output**

Create `ai_daily/outputs/newsletter.py`:
```python
"""Newsletter email generation and sending."""

import base64
from datetime import date, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Optional

from sqlalchemy.orm import Session

from ai_daily.config import config
from ai_daily.db import Article, DailySummary
from ai_daily.outputs.summary_generator import SummaryGenerator


class NewsletterOutput:
    """Generate and send newsletter emails."""

    def __init__(self, gmail_service=None):
        self.gmail_service = gmail_service
        self.summary_generator = SummaryGenerator()
        self.template_path = config.templates_dir / "ai_daily_news_email_template.html"

    def _load_template(self) -> str:
        """Load email template."""
        if self.template_path.exists():
            return self.template_path.read_text()
        # Fallback minimal template
        return """
        <html>
        <body>
            <h1>AI Daily Newsletter - {{date}}</h1>
            <h2>Summary</h2>
            <p>{{summary}}</p>
            <h2>Key Facts</h2>
            <ul>{{key_facts}}</ul>
            <h2>Articles</h2>
            {{articles}}
        </body>
        </html>
        """

    def _categorize_articles(self, articles: List[Article]) -> dict:
        """Categorize articles by topic."""
        categories = {
            "AI Research and Advances": [],
            "AI Products, Tools, and Repositories": [],
            "Data Science Techniques and Tips": [],
            "Industry News and Trends": [],
        }

        for article in articles:
            topic = article.topic or ""
            topic_lower = topic.lower()

            if any(word in topic_lower for word in ["research", "study", "advance", "breakthrough"]):
                categories["AI Research and Advances"].append(article)
            elif any(word in topic_lower for word in ["tool", "product", "repository", "framework"]):
                categories["AI Products, Tools, and Repositories"].append(article)
            elif any(word in topic_lower for word in ["tip", "technique", "guide", "tutorial"]):
                categories["Data Science Techniques and Tips"].append(article)
            else:
                categories["Industry News and Trends"].append(article)

        return categories

    def generate_html(self, summary: DailySummary, articles: List[Article]) -> str:
        """Generate HTML email content."""
        template = self._load_template()

        # Replace placeholders
        html = template.replace("{{date}}", datetime.now().strftime("%B %d, %Y"))
        html = html.replace("{{summary}}", summary.summary_text or "")
        html = html.replace("{{year}}", str(datetime.now().year))

        # Key facts
        key_facts_html = ""
        if summary.key_facts:
            for fact in summary.key_facts:
                key_facts_html += f"<li>{fact}</li>"
        html = html.replace("{{key_facts}}", key_facts_html)

        # Articles by category
        categories = self._categorize_articles(articles)
        articles_html = ""

        for category, cat_articles in categories.items():
            if cat_articles:
                articles_html += f"<h3>{category}</h3>"
                for article in cat_articles:
                    articles_html += f"""
                    <h4>{article.title}</h4>
                    <p>{article.content[:500]}...</p>
                    <p><a href="{article.url}">Read more</a></p>
                    """

        html = html.replace("{{articles}}", articles_html)

        return html

    async def send(
        self,
        session: Session,
        target_date: Optional[date] = None,
        recipients: Optional[List[str]] = None
    ) -> bool:
        """Generate and send newsletter.

        Args:
            session: Database session.
            target_date: Date to send newsletter for.
            recipients: List of email addresses. Defaults to config.

        Returns:
            True if sent successfully.
        """
        if not self.gmail_service:
            raise ValueError("Gmail service not initialized")

        if target_date is None:
            target_date = date.today()

        if recipients is None:
            recipients = config.recipients

        if not recipients:
            raise ValueError("No recipients configured")

        # Generate summary
        summary = await self.summary_generator.generate(session, target_date)

        # Get articles
        articles = self.summary_generator.get_articles_for_date(session, target_date)

        # Generate HTML
        html_content = self.generate_html(summary, articles)

        # Send to each recipient
        subject = f"AI-Daily Newsletter - {target_date.strftime('%B %d, %Y')}"

        for recipient in recipients:
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["To"] = recipient
            message["From"] = "me"

            part = MIMEText(html_content, "html")
            message.attach(part)

            raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
            self.gmail_service.users().messages().send(
                userId="me",
                body={"raw": raw}
            ).execute()

        return True
```

**Step 2: Update outputs __init__.py**

Update `ai_daily/outputs/__init__.py`:
```python
"""Output generators (newsletter, TTS, etc.)."""

from ai_daily.outputs.newsletter import NewsletterOutput
from ai_daily.outputs.summary_generator import SummaryGenerator

__all__ = ["NewsletterOutput", "SummaryGenerator"]
```

**Step 3: Verify**

Run: `.venv/bin/python -c "from ai_daily.outputs import NewsletterOutput; print('OK')"`
Expected: "OK"

**Step 4: Commit**

```bash
git add ai_daily/outputs/
git commit -m "feat(outputs): implement newsletter email output

- HTML generation from template
- Article categorization
- Gmail API integration for sending
- Configurable recipients"
```

---

### Task 15: Implement TTS Briefing Output

**Files:**
- Create: `ai_daily/outputs/tts_briefing.py`

**Step 1: Create TTS briefing output**

Create `ai_daily/outputs/tts_briefing.py`:
```python
"""Text-to-speech briefing generation."""

import json
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from openai import AsyncOpenAI
from sqlalchemy.orm import Session

from ai_daily.config import config
from ai_daily.db import DailySummary
from ai_daily.outputs.summary_generator import SummaryGenerator

# Pocket TTS import (may not be available)
try:
    from pocket_tts import TTSModel
    import scipy.io.wavfile
    POCKET_TTS_AVAILABLE = True
except ImportError:
    POCKET_TTS_AVAILABLE = False


class TTSBriefingOutput:
    """Generate audio briefings from daily summaries."""

    SCRIPT_PROMPT = """Convert this newsletter summary into a natural, conversational script
for a 2-3 minute audio briefing.

Guidelines:
- Start with a brief greeting and date
- Use conversational language, not formal writing
- Include natural transitions between topics
- End with a brief sign-off
- Keep it concise - aim for about 400-500 words

Output the script as plain text, ready to be read aloud."""

    def __init__(self):
        self.summary_generator = SummaryGenerator()
        self.output_dir = config.data_dir / "briefings"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if config.llm.provider == "ollama":
            self.llm_client = AsyncOpenAI(
                base_url=config.llm.ollama_base_url,
                api_key="ollama"
            )
        else:
            self.llm_client = AsyncOpenAI()

        self.tts_model = None
        self.voice_state = None

    def _init_tts(self, voice: str = "alba"):
        """Initialize TTS model lazily."""
        if not POCKET_TTS_AVAILABLE:
            raise RuntimeError("Pocket TTS not installed. Run: pip install pocket-tts")

        if self.tts_model is None:
            self.tts_model = TTSModel.load_model()
            self.voice_state = self.tts_model.get_state_for_audio_prompt(voice)

    async def generate_script(self, summary: DailySummary) -> str:
        """Generate spoken script from summary."""
        content = f"""Summary: {summary.summary_text}

Key Facts:
{chr(10).join(f'- {fact}' for fact in (summary.key_facts or []))}"""

        response = await self.llm_client.chat.completions.create(
            model=config.llm.model,
            messages=[
                {"role": "system", "content": self.SCRIPT_PROMPT},
                {"role": "user", "content": content}
            ],
        )

        return response.choices[0].message.content

    async def generate(
        self,
        session: Session,
        target_date: Optional[date] = None,
        voice: str = "alba"
    ) -> Path:
        """Generate audio briefing.

        Args:
            session: Database session.
            target_date: Date to generate briefing for.
            voice: Pocket TTS voice name.

        Returns:
            Path to generated audio file.
        """
        if target_date is None:
            target_date = date.today()

        # Get or generate summary
        summary = await self.summary_generator.generate(session, target_date)

        # Generate script
        script = await self.generate_script(summary)

        # Save script for reference
        script_path = self.output_dir / f"{target_date.isoformat()}_script.txt"
        script_path.write_text(script)

        # Generate audio
        self._init_tts(voice)
        audio = self.tts_model.generate_audio(self.voice_state, script)

        # Save audio
        audio_path = self.output_dir / f"{target_date.isoformat()}_briefing.wav"
        scipy.io.wavfile.write(str(audio_path), self.tts_model.sample_rate, audio.numpy())

        return audio_path
```

**Step 2: Update outputs __init__.py**

Update `ai_daily/outputs/__init__.py`:
```python
"""Output generators (newsletter, TTS, etc.)."""

from ai_daily.outputs.newsletter import NewsletterOutput
from ai_daily.outputs.summary_generator import SummaryGenerator
from ai_daily.outputs.tts_briefing import TTSBriefingOutput

__all__ = ["NewsletterOutput", "SummaryGenerator", "TTSBriefingOutput"]
```

**Step 3: Verify**

Run: `.venv/bin/python -c "from ai_daily.outputs import TTSBriefingOutput; print('OK')"`
Expected: "OK"

**Step 4: Commit**

```bash
git add ai_daily/outputs/
git commit -m "feat(outputs): implement TTS briefing output

- LLM-generated conversational script
- Pocket TTS integration with lazy loading
- Voice selection support
- Script saved alongside audio for reference"
```

---

## Phase 6: API Server

### Task 16: Implement FastAPI Server

**Files:**
- Create: `ai_daily/api/server.py`
- Create: `ai_daily/api/routes.py`

**Step 1: Create API routes**

Create `ai_daily/api/routes.py`:
```python
"""API route handlers."""

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ai_daily.db import Article, DailySummary, JobRun, Source, get_session

router = APIRouter()


# Pydantic models for responses
class ArticleResponse(BaseModel):
    id: int
    title: str
    content: str
    url: Optional[str]
    topic: Optional[str]
    published_at: Optional[datetime]
    source_name: Optional[str] = None

    class Config:
        from_attributes = True


class SummaryResponse(BaseModel):
    date: datetime
    summary_text: Optional[str]
    key_facts: Optional[List[str]]

    class Config:
        from_attributes = True


class SourceResponse(BaseModel):
    id: int
    type: str
    name: str
    enabled: bool

    class Config:
        from_attributes = True


class JobResponse(BaseModel):
    id: int
    job_name: str
    started_at: datetime
    finished_at: Optional[datetime]
    status: Optional[str]

    class Config:
        from_attributes = True


# Dependency for DB session
def get_db():
    with get_session() as session:
        yield session


# Article endpoints
@router.get("/articles", response_model=List[ArticleResponse])
def list_articles(
    q: Optional[str] = Query(None, description="Search query"),
    topic: Optional[str] = Query(None, description="Filter by topic"),
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    limit: int = Query(20, le=100),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    """List articles with optional filters."""
    stmt = select(Article)

    if q:
        stmt = stmt.where(or_(
            Article.title.ilike(f"%{q}%"),
            Article.content.ilike(f"%{q}%"),
        ))

    if topic:
        stmt = stmt.where(Article.topic == topic)

    if from_date:
        stmt = stmt.where(Article.published_at >= datetime.combine(from_date, datetime.min.time()))

    if to_date:
        stmt = stmt.where(Article.published_at <= datetime.combine(to_date, datetime.max.time()))

    stmt = stmt.order_by(Article.published_at.desc()).offset(offset).limit(limit)

    articles = db.execute(stmt).scalars().all()
    return articles


@router.get("/articles/{article_id}", response_model=ArticleResponse)
def get_article(article_id: int, db: Session = Depends(get_db)):
    """Get a single article by ID."""
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@router.get("/search", response_model=List[ArticleResponse])
def semantic_search(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, le=50),
    db: Session = Depends(get_db),
):
    """Semantic search using embeddings.

    Note: Full vector search requires embedding the query.
    This is a placeholder that falls back to keyword search.
    """
    # TODO: Implement proper vector search
    # For now, fall back to keyword search
    stmt = select(Article).where(or_(
        Article.title.ilike(f"%{q}%"),
        Article.content.ilike(f"%{q}%"),
    )).order_by(Article.published_at.desc()).limit(limit)

    return db.execute(stmt).scalars().all()


# Summary endpoints
@router.get("/summary/{target_date}", response_model=SummaryResponse)
def get_summary(target_date: date, db: Session = Depends(get_db)):
    """Get daily summary for a specific date."""
    stmt = select(DailySummary).where(
        DailySummary.date == datetime.combine(target_date, datetime.min.time())
    )
    summary = db.execute(stmt).scalar_one_or_none()

    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found for this date")

    return summary


# Source endpoints
@router.get("/sources", response_model=List[SourceResponse])
def list_sources(db: Session = Depends(get_db)):
    """List all sources."""
    return db.execute(select(Source)).scalars().all()


# Job endpoints
@router.get("/jobs", response_model=List[JobResponse])
def list_jobs(
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    """List recent job runs."""
    stmt = select(JobRun).order_by(JobRun.started_at.desc()).limit(limit)
    return db.execute(stmt).scalars().all()
```

**Step 2: Create main server**

Create `ai_daily/api/server.py`:
```python
"""FastAPI server configuration."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai_daily.api.routes import router

app = FastAPI(
    title="AI Daily Summary API",
    description="API for the AI news aggregation platform",
    version="0.2.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router, prefix="/api/v1")


@app.get("/")
def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "ai-daily-summary"}


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "healthy"}
```

**Step 3: Update api __init__.py**

Update `ai_daily/api/__init__.py`:
```python
"""API server components."""

from ai_daily.api.server import app

__all__ = ["app"]
```

**Step 4: Verify**

Run: `.venv/bin/python -c "from ai_daily.api import app; print('OK')"`
Expected: "OK"

**Step 5: Commit**

```bash
git add ai_daily/api/
git commit -m "feat(api): implement FastAPI server

Endpoints:
- GET /api/v1/articles - list with filters
- GET /api/v1/articles/{id} - single article
- GET /api/v1/search - semantic search (placeholder)
- GET /api/v1/summary/{date} - daily summary
- GET /api/v1/sources - list sources
- GET /api/v1/jobs - recent job runs
- CORS enabled"
```

---

## Phase 7: Integration & Testing

### Task 17: Add Integration Tests

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_pipeline.py`

**Step 1: Create test fixtures**

Create `tests/__init__.py`:
```python
"""Tests for AI Daily Summary."""
```

Create `tests/conftest.py`:
```python
"""Pytest configuration and fixtures."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ai_daily.db.models import Base


@pytest.fixture(scope="session")
def engine():
    """Create test database engine."""
    # Use SQLite for testing
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """Create test database session."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()
```

**Step 2: Create pipeline tests**

Create `tests/test_pipeline.py`:
```python
"""Tests for ETL pipeline components."""

import pytest

from ai_daily.db.models import Article, Source
from ai_daily.etl.transformers import compute_content_hash
from ai_daily.etl.types import RawContent


def test_compute_content_hash():
    """Test content hash computation."""
    hash1 = compute_content_hash("Title", "Content here")
    hash2 = compute_content_hash("Title", "Content here")
    hash3 = compute_content_hash("Different", "Content here")

    assert hash1 == hash2
    assert hash1 != hash3
    assert len(hash1) == 32  # MD5 hex length


def test_raw_content_creation():
    """Test RawContent dataclass."""
    content = RawContent(
        external_id="test-123",
        title="Test Article",
        content="This is test content",
        url="https://example.com",
    )

    assert content.external_id == "test-123"
    assert content.title == "Test Article"
    assert content.metadata == {}


def test_source_model(session):
    """Test Source model creation."""
    source = Source(
        type="newsletter",
        name="Test Newsletter",
        config={"whitelist": ["test@example.com"]},
        enabled=True,
    )
    session.add(source)
    session.commit()

    assert source.id is not None
    assert source.type == "newsletter"
    assert source.config["whitelist"] == ["test@example.com"]


def test_article_model(session):
    """Test Article model creation."""
    source = Source(type="newsletter", name="Test")
    session.add(source)
    session.commit()

    article = Article(
        source_id=source.id,
        external_id="article-1",
        title="Test Article",
        content="Test content",
        topic="AI Research and Advances",
        content_hash=compute_content_hash("Test Article", "Test content"),
    )
    session.add(article)
    session.commit()

    assert article.id is not None
    assert article.source_id == source.id
```

**Step 3: Update pyproject.toml for pytest**

Add to `pyproject.toml`:
```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All tests pass

**Step 5: Commit**

```bash
git add tests/ pyproject.toml
git commit -m "test: add integration tests for ETL pipeline

- Test fixtures with SQLite in-memory DB
- Content hash computation tests
- RawContent dataclass tests
- Source and Article model tests"
```

---

### Task 18: Add Database Seed Script

**Files:**
- Create: `ai_daily/db/seed.py`

**Step 1: Create seed script**

Create `ai_daily/db/seed.py`:
```python
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
```

**Step 2: Add seed command to CLI**

Update `ai_daily/cli.py`, add after the `init` command:
```python
@main.command()
def seed():
    """Seed database with initial sources from config.json."""
    from ai_daily.db.seed import seed_sources
    seed_sources()
    console.print("[green]Database seeded successfully![/green]")
```

**Step 3: Verify**

Run: `.venv/bin/python -c "from ai_daily.db.seed import seed_sources; print('OK')"`
Expected: "OK"

**Step 4: Commit**

```bash
git add ai_daily/db/seed.py ai_daily/cli.py
git commit -m "feat(db): add database seed script

- Seed newsletter source from config.json whitelist
- Seed GitHub source with default config
- CLI command: ai-daily seed"
```

---

## Phase 8: Final Integration

### Task 19: Update Main Entry Point

**Files:**
- Create: `ai_daily/main.py`

**Step 1: Create unified main entry point**

Create `ai_daily/main.py`:
```python
"""Main entry point for running the full pipeline."""

import asyncio
import logging
from datetime import date

from ai_daily.config import config
from ai_daily.db import get_session, init_db
from ai_daily.db.seed import seed_sources
from ai_daily.etl import ETLPipeline
from ai_daily.etl.extractors.gmail import GmailExtractor
from ai_daily.outputs import NewsletterOutput, TTSBriefingOutput

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_daily_pipeline():
    """Run the complete daily pipeline."""
    logger.info("Starting AI Daily pipeline...")

    # Initialize database if needed
    init_db()
    seed_sources()

    # Run ETL
    pipeline = ETLPipeline()
    metrics = await pipeline.run_all()
    logger.info(f"ETL complete: {metrics}")

    # Generate and send newsletter
    with get_session() as session:
        # Get Gmail service from extractor
        gmail_extractor = GmailExtractor()

        newsletter = NewsletterOutput(gmail_service=gmail_extractor.service)
        await newsletter.send(session, target_date=date.today())
        logger.info("Newsletter sent")

        # Generate TTS briefing (optional)
        try:
            tts = TTSBriefingOutput()
            audio_path = await tts.generate(session, target_date=date.today())
            logger.info(f"TTS briefing generated: {audio_path}")
        except Exception as e:
            logger.warning(f"TTS generation skipped: {e}")

    logger.info("Daily pipeline complete!")


def main():
    """Run the pipeline."""
    asyncio.run(run_daily_pipeline())


if __name__ == "__main__":
    main()
```

**Step 2: Add run-all command to CLI**

Update `ai_daily/cli.py`, add new command:
```python
@main.command("run-daily")
def run_daily():
    """Run the complete daily pipeline (ETL + newsletter + TTS)."""
    from ai_daily.main import run_daily_pipeline
    asyncio.run(run_daily_pipeline())
```

**Step 3: Verify**

Run: `.venv/bin/python -c "from ai_daily.main import run_daily_pipeline; print('OK')"`
Expected: "OK"

**Step 4: Commit**

```bash
git add ai_daily/main.py ai_daily/cli.py
git commit -m "feat: add unified daily pipeline runner

- Combines ETL, newsletter, and TTS generation
- Database initialization and seeding
- CLI command: ai-daily run-daily"
```

---

### Task 20: Create launchd Plist Files

**Files:**
- Create: `launchd/com.aidaily.etl.plist`
- Create: `launchd/com.aidaily.newsletter.plist`

**Step 1: Create launchd directory and ETL plist**

```bash
mkdir -p launchd
```

Create `launchd/com.aidaily.etl.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.aidaily.etl</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/project/.venv/bin/python</string>
        <string>-m</string>
        <string>ai_daily.cli</string>
        <string>run</string>
        <string>all</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/project</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>6</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/path/to/project/logs/etl.log</string>
    <key>StandardErrorPath</key>
    <string>/path/to/project/logs/etl_error.log</string>
</dict>
</plist>
```

Create `launchd/com.aidaily.newsletter.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.aidaily.newsletter</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/project/.venv/bin/python</string>
        <string>-m</string>
        <string>ai_daily.cli</string>
        <string>run-daily</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/project</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>7</integer>
        <key>Minute</key>
        <integer>30</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/path/to/project/logs/newsletter.log</string>
    <key>StandardErrorPath</key>
    <string>/path/to/project/logs/newsletter_error.log</string>
</dict>
</plist>
```

**Step 2: Create installation script**

Create `launchd/install.sh`:
```bash
#!/bin/bash
# Install launchd plists for AI Daily

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"

# Update paths in plists
for plist in "$PROJECT_DIR/launchd/"*.plist; do
    sed -i '' "s|/path/to/project|$PROJECT_DIR|g" "$plist"
done

# Copy to LaunchAgents
cp "$PROJECT_DIR/launchd/"*.plist ~/Library/LaunchAgents/

# Load agents
launchctl load ~/Library/LaunchAgents/com.aidaily.etl.plist
launchctl load ~/Library/LaunchAgents/com.aidaily.newsletter.plist

echo "Installed and loaded launchd agents"
echo "ETL runs daily at 6:00 AM"
echo "Newsletter runs daily at 7:30 AM"
```

**Step 3: Make script executable**

```bash
chmod +x launchd/install.sh
```

**Step 4: Commit**

```bash
git add launchd/
git commit -m "feat: add launchd scheduling configuration

- ETL job runs at 6:00 AM
- Newsletter job runs at 7:30 AM
- Installation script for easy setup
- Logs to project logs directory"
```

---

### Task 21: Final Cleanup and Documentation

**Files:**
- Update: `README.md` (if exists) or create basic documentation

**Step 1: Update .gitignore**

Add to `.gitignore`:
```
# Database
*.db

# Logs
logs/

# Data
data/

# Briefings
briefings/

# Environment
.env
```

**Step 2: Final commit**

```bash
git add .gitignore
git commit -m "chore: update gitignore for data platform

Ignore database files, logs, data directories"
```

**Step 3: Create final summary commit**

```bash
git log --oneline -20
```

Review commits and ensure all phases are complete.

---

## Summary

This plan transforms the AI Daily Summary project into a multi-layered data platform:

1. **Phase 1**: Project scaffolding and database models
2. **Phase 2**: ETL extractors (Gmail, GitHub, Crawler)
3. **Phase 3**: ETL transformers (LLM parser, embedder, deduplicator)
4. **Phase 4**: CLI with Rich output
5. **Phase 5**: Business outputs (newsletter, TTS)
6. **Phase 6**: FastAPI server
7. **Phase 7**: Integration tests
8. **Phase 8**: Final integration and scheduling

Total: 21 tasks across 8 phases.
