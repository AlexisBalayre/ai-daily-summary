# AI Daily Summary - Data Platform Design

**Date:** 2026-02-03
**Status:** Approved

## Overview

Evolve the AI Daily Summary project from a "process and send" newsletter tool into a proper data platform with ETL pipelines, persistent storage, indexing, and multiple business outputs.

### Goals

1. **ETL Pipeline Layer** - Extract from multiple sources, transform with LLM, load to PostgreSQL
2. **Data Indexing** - Full-text and semantic search across all historical content
3. **Multiple Outputs** - Newsletter, TTS audio briefing, API/MCP server, search interface
4. **Trend Analysis** - Track topics over time, understand what's gaining attention
5. **Local-first** - Everything runs on a Mac Mini

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA LAYER                                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                 PostgreSQL + pgvector                     │   │
│  │  • articles (content, embeddings, metadata)               │   │
│  │  • sources (newsletters, github, crawlers)                │   │
│  │  • job_runs (observability)                               │   │
│  │  • daily_summaries (cached outputs)                       │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │
┌─────────────────────────────────────────────────────────────────┐
│                        ETL LAYER                                 │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐                 │
│  │  Extract   │→ │ Transform  │→ │    Load    │                 │
│  │ Gmail API  │  │ LLM Parse  │  │ PostgreSQL │                 │
│  │ GitHub     │  │ Embed      │  │ + pgvector │                 │
│  │ Crawlers   │  │ Categorize │  │            │                 │
│  └────────────┘  └────────────┘  └────────────┘                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     BUSINESS LAYER                               │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐             │
│  │  Newsletter  │ │ TTS Briefing │ │  API / MCP   │             │
│  │    Email     │ │  Pocket TTS  │ │   Server     │             │
│  └──────────────┘ └──────────────┘ └──────────────┘             │
│                                     ┌──────────────┐             │
│                                     │ Search UI    │             │
│                                     │  (Web/CLI)   │             │
│                                     └──────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

### Key Principles

- **Separation of concerns**: ETL writes to database, business layer reads from it
- **Single source of truth**: PostgreSQL holds all data and state
- **Idempotent operations**: Re-running ETL or outputs is safe
- **Local-first**: Everything runs on the Mac Mini

---

## Data Model (PostgreSQL Schema)

```sql
-- Sources: where content comes from
CREATE TABLE sources (
    id SERIAL PRIMARY KEY,
    type VARCHAR(50) NOT NULL,        -- 'newsletter', 'github', 'crawler'
    name VARCHAR(255) NOT NULL,       -- 'Ben's Bites', 'Hacker News', etc.
    config JSONB,                     -- source-specific settings
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Articles: the core content store
CREATE TABLE articles (
    id SERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES sources(id),
    external_id VARCHAR(255),         -- dedup key (URL hash, email ID, etc.)
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    url TEXT,
    author VARCHAR(255),
    published_at TIMESTAMP,
    ingested_at TIMESTAMP DEFAULT NOW(),

    -- Categorization
    topic VARCHAR(100),               -- 'AI Research', 'Industry News', etc.
    tags TEXT[],                      -- flexible tagging

    -- Vector search
    embedding vector(1536),           -- for semantic search

    -- Deduplication
    content_hash VARCHAR(64),         -- MD5 for exact dedup

    UNIQUE(source_id, external_id)
);

-- Daily summaries: cached generated outputs
CREATE TABLE daily_summaries (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    summary_text TEXT,                -- LLM-generated summary
    key_facts JSONB,                  -- structured highlights
    article_ids INTEGER[],            -- which articles were included
    created_at TIMESTAMP DEFAULT NOW()
);

-- Job runs: observability
CREATE TABLE job_runs (
    id SERIAL PRIMARY KEY,
    job_name VARCHAR(100) NOT NULL,   -- 'etl_gmail', 'etl_github', etc.
    started_at TIMESTAMP DEFAULT NOW(),
    finished_at TIMESTAMP,
    status VARCHAR(20),               -- 'running', 'success', 'failed'
    metrics JSONB,                    -- articles_processed, etc.
    error_message TEXT
);

-- Indexes
CREATE INDEX idx_articles_published ON articles(published_at DESC);
CREATE INDEX idx_articles_topic ON articles(topic);
CREATE INDEX idx_articles_embedding ON articles USING ivfflat (embedding vector_cosine_ops);
```

### Design Decisions

- **JSONB for flexibility**: Source configs and metrics vary by type
- **Vector index**: IVFFlat for fast approximate nearest neighbor search
- **Content hash**: Prevents duplicate articles across sources
- **Daily summaries cached**: Don't regenerate unless needed

---

## ETL Layer - Extractors

Pluggable system where each source type has its own extractor.

```
lib/extractors/
├── base.py           # Abstract base class
├── gmail.py          # Newsletter extraction
├── github.py         # Trending repos
└── crawler.py        # Website monitoring
```

### Base Interface

```python
class BaseExtractor(ABC):
    @abstractmethod
    async def extract(self, source: Source) -> list[RawContent]:
        """Fetch new content from source, return raw items."""
        pass

    @abstractmethod
    def get_external_id(self, item: RawContent) -> str:
        """Return unique ID for deduplication."""
        pass
```

### Crawler Configuration

Each crawled source stores config in `sources.config` JSONB:

```json
{
  "url": "https://news.ycombinator.com/best",
  "selectors": {
    "items": ".athing",
    "title": ".titleline > a",
    "link": ".titleline > a@href"
  },
  "schedule": "every_6_hours",
  "content_mode": "fetch_full"
}
```

### Content Modes

- `summary_only`: Just title + link (lightweight)
- `fetch_full`: Follow link and extract article content (better for search)

---

## ETL Layer - Transform

```
lib/transformers/
├── llm_parser.py      # Extract structured data
├── embedder.py        # Generate vector embeddings
├── categorizer.py     # Topic classification
└── deduplicator.py    # Similarity-based grouping
```

### Transform Pipeline

```
RawContent
    │
    ▼
┌─────────────────┐
│   LLM Parser    │  → Structured article
└─────────────────┘
    │
    ▼
┌─────────────────┐
│   Deduplicator  │  → Skip if duplicate
└─────────────────┘
    │
    ▼
┌─────────────────┐
│    Embedder     │  → Generate vector
└─────────────────┘
    │
    ▼
┌─────────────────┐
│  Categorizer    │  → Assign topic + tags
└─────────────────┘
    │
    ▼
Ready for Load
```

### Embedding Options

| Option | Dimensions | Speed | Quality |
|--------|-----------|-------|---------|
| OpenAI `text-embedding-3-small` | 1536 | Fast (API) | Excellent |
| Ollama `nomic-embed-text` | 768 | Local | Good |
| Ollama `mxbai-embed-large` | 1024 | Local | Better |

**Recommendation:** Start with OpenAI embeddings, switch to Ollama for fully offline operation later.

### Deduplication Strategy

1. **Exact match**: Skip if `content_hash` exists
2. **Semantic similarity**: If cosine similarity > 0.92, flag as duplicate or link as "related"

---

## Business Layer - Outputs

```
lib/outputs/
├── newsletter.py      # Email
├── tts_briefing.py    # Audio summary
├── api_server.py      # REST/MCP server
└── search_cli.py      # CLI search
```

### Newsletter

- Query today's articles from DB
- Use cached `daily_summaries` if available
- Same HTML template approach

### TTS Briefing

```python
from pocket_tts import TTSModel

def generate_briefing(date: date) -> Path:
    summary = get_daily_summary(date)
    script = llm_generate_spoken_script(summary)  # conversational

    tts = TTSModel.load_model()
    voice = tts.get_state_for_audio_prompt("alba")
    audio = tts.generate_audio(voice, script)

    output_path = DATA_DIR / f"briefings/{date}.wav"
    scipy.io.wavfile.write(output_path, tts.sample_rate, audio.numpy())
    return output_path
```

### API Server (FastAPI)

- `GET /articles?q=&topic=&from=&to=` - search/filter
- `GET /articles/{id}` - single article
- `GET /search?q=` - semantic vector search
- `GET /trends?topic=&days=` - trend analysis
- `GET /summary/{date}` - daily summary

### MCP Server

Expose capabilities as tools for Claude:
- "Search my knowledge base for X"
- "What were the top AI stories last week?"

---

## Scheduling & Observability

### Daily Schedule (launchd)

| Time | Job | Description |
|------|-----|-------------|
| 06:00 | `etl_gmail` | Fetch newsletter emails |
| 06:15 | `etl_github` | Scrape trending repos |
| 06:30 | `etl_crawlers` | Run website crawlers |
| 07:00 | `generate_summary` | Create daily summary |
| 07:30 | `output_newsletter` | Send email |
| 07:45 | `output_tts` | Generate audio briefing |

### Job Tracking

```python
@contextmanager
def track_job(job_name: str):
    run = JobRun.create(job_name=job_name, status="running")
    try:
        yield run
        run.status = "success"
    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)
        raise
    finally:
        run.finished_at = datetime.now()
        run.save()
```

### Status CLI

```bash
$ ai-daily status
Last 24h:
  ✓ etl_gmail      06:00  12 articles   2.3s
  ✓ etl_github     06:15  25 repos      1.1s
  ✓ etl_crawlers   06:30  8 articles    4.2s
  ✓ generate_summary 07:00              1.8s
  ✓ output_newsletter 07:30  3 recipients
  ✓ output_tts     07:45  briefing.wav  12.4s
```

---

## Project Structure

```
ai-daily-summary/
├── ai_daily/
│   ├── __init__.py
│   ├── cli.py                    # Main CLI entry point
│   ├── config.py                 # Settings, env vars
│   │
│   ├── db/
│   │   ├── models.py             # SQLAlchemy models
│   │   ├── connection.py         # DB session management
│   │   └── migrations/           # Alembic migrations
│   │
│   ├── etl/
│   │   ├── extractors/
│   │   │   ├── base.py
│   │   │   ├── gmail.py
│   │   │   ├── github.py
│   │   │   └── crawler.py
│   │   ├── transformers/
│   │   │   ├── llm_parser.py
│   │   │   ├── embedder.py
│   │   │   └── categorizer.py
│   │   └── pipeline.py           # Orchestrates E→T→L
│   │
│   ├── outputs/
│   │   ├── newsletter.py
│   │   ├── tts_briefing.py
│   │   └── summary_generator.py
│   │
│   ├── api/
│   │   ├── server.py             # FastAPI app
│   │   ├── routes.py
│   │   └── mcp_server.py         # MCP tool definitions
│   │
│   └── search/
│       ├── semantic.py           # Vector search
│       └── cli.py                # Search CLI interface
│
├── templates/
│   ├── email_newsletter.html
│   └── email_github.html
│
├── data/                         # Local file storage
├── logs/
├── launchd/                      # Plist files for scheduling
│
├── pyproject.toml
├── .env
└── config.json                   # Source definitions
```

### CLI Commands

```bash
ai-daily run etl_gmail          # Run single ETL job
ai-daily run all                # Run full pipeline
ai-daily status                 # Show recent job runs
ai-daily search "transformers"  # Semantic search
ai-daily serve                  # Start API server
```

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| Database | PostgreSQL + pgvector |
| ORM | SQLAlchemy + Alembic |
| API | FastAPI |
| TTS | Pocket TTS |
| LLM | OpenAI / Ollama |
| Embeddings | OpenAI text-embedding-3-small |
| Scheduling | macOS launchd |
| Package Manager | uv |

---

## Migration Path

1. Set up PostgreSQL + pgvector locally
2. Create database schema with Alembic
3. Migrate existing JSON data to PostgreSQL
4. Refactor extractors to use new interface
5. Add transform pipeline with embeddings
6. Update newsletter output to read from DB
7. Add TTS briefing output
8. Add API server
9. Add search CLI
10. Set up launchd scheduling
