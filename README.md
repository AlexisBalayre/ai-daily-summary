# AI Daily Summary

AI-powered daily summary and newsletter generation platform. Aggregates content from Gmail newsletters, GitHub trending repositories, and web sources, then generates summaries using local LLMs.

## Features

- **Multi-source ETL Pipeline**: Collect articles from Gmail newsletters, GitHub trending, and web crawlers
- **Semantic Search**: PostgreSQL with pgvector for embedding-based article search
- **Local LLM Processing**: Use Ollama for summarization and embeddings (no API costs)
- **Newsletter Generation**: HTML email summaries sent via Gmail API
- **TTS Audio Briefings**: Text-to-speech audio summaries using Pocket TTS
- **REST API**: FastAPI endpoints for articles, summaries, and search
- **Docker Deployment**: Single command deployment with Docker Compose

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Gmail API      │     │  GitHub         │     │  Web Crawler    │
│  (newsletters)  │     │  (trending)     │     │  (RSS/sites)    │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 ▼
                    ┌────────────────────────┐
                    │     ETL Pipeline       │
                    │  (parse, embed, store) │
                    └───────────┬────────────┘
                                │
                    ┌───────────▼────────────┐
                    │   PostgreSQL + pgvector │
                    │   (articles, embeddings)│
                    └───────────┬────────────┘
                                │
         ┌──────────────────────┼──────────────────────┐
         ▼                      ▼                      ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│   Newsletter    │   │   TTS Briefing  │   │    REST API     │
│   (Gmail)       │   │   (Audio)       │   │   (FastAPI)     │
└─────────────────┘   └─────────────────┘   └─────────────────┘
```

## Prerequisites

- **Docker & Docker Compose** (for containerized deployment)
- **Ollama** running on host machine with models:
  - `qwen3:30b-a3b` - LLM for summarization
  - `qwen3-embedding:8b` - Embedding model for semantic search
- **Gmail API credentials** (for newsletter sending)

### Install Ollama Models

```bash
# Install the recommended models
ollama pull qwen3:8b
ollama pull qwen3-embedding:8b
```

## Quick Start

### 1. Clone and Configure

```bash
git clone https://github.com/AlexisBalayre/ai-daily-summary.git
cd ai-daily-summary

# Copy and edit environment configuration
cp .env.example .env
# Edit .env with your Gmail credentials and preferences
```

### 2. Start with Docker Compose

```bash
# Start PostgreSQL and the application
docker compose up -d

# View logs
docker compose logs -f app
```

The application will:
- Initialize the database with migrations
- Seed default sources (Gmail, GitHub, web)
- Start cron jobs for scheduled runs
- Start the FastAPI server on port 8000

### Scheduled Jobs (inside container)

- **06:00** - ETL pipeline (collect and process articles)
- **07:30** - Generate and send newsletter

## CLI Commands

```bash
# Initialize database
ai-daily init

# Seed default sources
ai-daily seed

# Run full pipeline (ETL + newsletter + TTS)
ai-daily run [--skip-etl] [--skip-newsletter] [--skip-tts]

# Run only ETL
ai-daily run-daily

# Check system status
ai-daily status

# Semantic search
ai-daily search "machine learning transformers" [--limit 10]

# Manage sources
ai-daily source list
ai-daily source add --name "Tech News" --type web --config '{"url": "..."}'
ai-daily source remove <source-id>

# Start API server
ai-daily serve [--host 0.0.0.0] [--port 8000]
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/articles` | GET | List articles (with pagination) |
| `/articles/{id}` | GET | Get article by ID |
| `/articles/search` | GET | Semantic search (`?q=query`) |
| `/summaries` | GET | List daily summaries |
| `/summaries/{id}` | GET | Get summary by ID |
| `/summaries/latest` | GET | Get latest summary |

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_HOST` | PostgreSQL host | `localhost` |
| `DB_PORT` | PostgreSQL port | `5432` |
| `DB_NAME` | Database name | `ai_daily` |
| `DB_USER` | Database user | `postgres` |
| `DB_PASSWORD` | Database password | `postgres` |
| `LLM_PROVIDER` | LLM provider | `ollama` |
| `LLM_MODEL` | LLM model for summaries | `qwen3:30b-a3b` |
| `EMBEDDING_MODEL` | Model for embeddings | `qwen3-embedding:8b` |
| `OLLAMA_BASE_URL` | Ollama API URL | `http://localhost:11434` |
| `OPENAI_API_KEY` | OpenAI key (fallback) | - |
| `GMAIL_CLIENT_ID` | Gmail OAuth client ID | - |
| `GMAIL_CLIENT_SECRET` | Gmail OAuth secret | - |
| `GMAIL_PROJECT_ID` | Gmail project ID | - |
| `RECIPIENTS` | Newsletter recipients | - |
| `GITHUB_COOKIE` | GitHub session cookie | - |

## Orchestrator

The orchestrator manages job scheduling with cron expressions, automatic retries, and failure notifications.

### Scheduled Jobs

| Job | Default Schedule | Description |
|-----|-----------------|-------------|
| `etl` | `0 */4 * * *` | Collect articles every 4 hours |
| `tts` | `0 9 * * *` | Generate TTS briefing at 9:00 AM |
| `newsletter` | `0 14 * * *` | Send newsletter at 2:00 PM |

### Orchestrator Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `ETL_SCHEDULE` | ETL job schedule (cron) | `0 */4 * * *` |
| `TTS_SCHEDULE` | TTS job schedule (cron) | `0 9 * * *` |
| `NEWSLETTER_SCHEDULE` | Newsletter schedule (cron) | `0 14 * * *` |
| `RETRY_MAX_ATTEMPTS` | Max retry attempts | `3` |
| `RETRY_BASE_DELAY` | Initial retry delay (seconds) | `10` |
| `RETRY_MULTIPLIER` | Delay multiplier | `3` |

### Orchestrator CLI Commands

```bash
# Start orchestrator (foreground)
ai-daily orchestrator start

# Show scheduled jobs and recent runs
ai-daily orchestrator status

# Manually trigger a job
ai-daily orchestrator trigger etl
ai-daily orchestrator trigger newsletter
ai-daily orchestrator trigger tts
```

### Retry Behavior

Jobs retry with exponential backoff:
- Attempt 1: immediate
- Attempt 2: after 10 seconds
- Attempt 3: after 30 seconds (10 × 3)

On final failure, an email alert is sent to configured recipients.

### Model Recommendations

For best results with local inference:

| Use Case | Recommended Model | Notes |
|----------|-------------------|-------|
| Summarization | `qwen3:30b-a3b` | Best quality/speed balance |
| Embeddings | `qwen3-embedding:8b` | 1024 dimensions |
| Alternative LLM | `llama3.3:70b` | Higher quality, slower |
| Lightweight LLM | `qwen3:8b` | Faster, less capable |

## Development

### Local Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Start PostgreSQL (via Docker)
docker compose up -d postgres

# Initialize database
ai-daily init
ai-daily seed

# Run tests
pytest
```

### Project Structure

```
ai_daily/
├── api/           # FastAPI routes
├── db/            # SQLAlchemy models and database
├── etl/           # ETL pipeline and collectors
├── llm/           # LLM client (Ollama/OpenAI)
├── outputs/       # Newsletter and TTS generation
├── cli.py         # CLI commands
├── config.py      # Configuration
└── main.py        # Pipeline runner

templates/         # Email HTML templates
tests/             # Test suite
docker-compose.yml # Container orchestration
Dockerfile         # Application container
```

## Gmail API Setup

1. Create a project in [Google Cloud Console](https://console.cloud.google.com/)
2. Enable the Gmail API
3. Create OAuth 2.0 credentials (Desktop application)
4. Download credentials and set in `.env`:
   - `GMAIL_CLIENT_ID`
   - `GMAIL_CLIENT_SECRET`
   - `GMAIL_PROJECT_ID`
5. On first run, complete OAuth flow to generate `token.json`

## License

MIT
