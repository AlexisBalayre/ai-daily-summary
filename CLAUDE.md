# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI Daily Summary is an AI-powered news aggregation platform that collects content from Gmail newsletters, GitHub trending repos, RSS feeds, and web crawlers, then generates summaries and newsletters using LLMs (Google Gemini or Ollama).

## Common Commands

```bash
# Install dependencies (uses uv)
uv sync

# Run all tests
uv run pytest

# Run single test file
uv run pytest tests/test_enrichment.py -v

# Run specific test
uv run pytest tests/test_enrichment.py::TestEnrichmentProcessor::test_enrichment_processor_init -v

# Start API server (port 8000)
uv run ai-daily api

# Run ETL jobs
uv run ai-daily run gmail      # Gmail newsletters
uv run ai-daily run rss        # RSS feeds
uv run ai-daily run github     # GitHub trending
uv run ai-daily run enrichment # Article enrichment (LLM classification + dedup)
uv run ai-daily run all        # Full pipeline

# Database migrations
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "description"

# Orchestrator (scheduled jobs)
uv run ai-daily orchestrator start
uv run ai-daily orchestrator status
uv run ai-daily orchestrator trigger etl

# Build frontend (React dashboard)
cd frontend && npm install && npm run build
```

## Architecture

### ETL Pipeline Flow
```
Sources (Gmail/RSS/GitHub/Crawler)
    → Extractors (ai_daily/etl/extractors/)
    → RawContent objects
    → Transformers (dedup, embeddings, LLM parsing)
    → Articles stored in PostgreSQL + pgvector
    → Enrichment job (classification, summaries, semantic dedup)
    → Outputs (Newsletter, TTS, API)
```

### Key Modules

- **`ai_daily/etl/extractors/`** - Source-specific extractors (gmail.py, rss.py, github.py, crawler.py) all inherit from `BaseExtractor`
- **`ai_daily/etl/enrichment.py`** - Post-ingestion enrichment: LLM classification (AI-related or not), summary generation, semantic duplicate detection via embeddings
- **`ai_daily/etl/transformers/`** - Content transformers: `embedder.py` (Google Gemini embeddings), `llm_parser.py` (article parsing), `deduplicator.py` (content hash dedup)
- **`ai_daily/db/models.py`** - SQLAlchemy models: Source, Article, DailySummary, JobRun
- **`ai_daily/orchestrator/`** - Job scheduling with cron expressions, retries, and failure notifications
- **`ai_daily/api/`** - FastAPI server with routes for articles, sources, summaries, whitelist management
- **`ai_daily/outputs/`** - Newsletter and TTS generation

### Database

PostgreSQL with pgvector extension for semantic search. Key tables:
- `articles` - Content with embeddings (768-dim vectors), enrichment fields (summary, category, is_ai_related)
- `sources` - Newsletter senders, RSS feeds, crawlers
- `daily_summaries` - Cached daily summaries
- `job_runs` - Job execution history

### Frontend

React + Tailwind CSS dashboard at `frontend/`. Built assets go to `ai_daily/api/static/` and are served by FastAPI.

### Configuration

- **`config.json`** - Newsletter sender whitelist
- **`.env`** - Environment variables (DB, LLM, Gmail credentials)
- **`ai_daily/config.py`** - Dataclass-based config with env var overrides

## Testing Patterns

Tests use pytest with pytest-asyncio. Mock external services (LLM, embeddings) in tests. Test fixtures in `tests/conftest.py` provide SQLite-based test database sessions.

```python
# Async test example
@pytest.mark.asyncio
async def test_something(mocker):
    mocker.patch('ai_daily.etl.enrichment.embed_text', return_value=[0.1] * 768)
    # ... test code
```

## Scheduled Jobs

| Job | Schedule | Description |
|-----|----------|-------------|
| etl | `0 */4 * * *` | Collect articles from all sources |
| enrichment | `30 */4 * * *` | Classify and deduplicate articles |
| newsletter | `0 14 * * *` | Send daily newsletter |
| tts | `0 9 * * *` | Generate audio briefing |
