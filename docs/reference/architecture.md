# Architecture (Reference)

The shape of this project: its components, where they live, and how a request or job flows
through them. This page describes *what is*; rationale belongs in [`explanation/`](../explanation/),
the dated design notes in [`design/`](../design/), and hard-to-reverse decisions in
[`adr/`](../adr/README.md). Coding rules live in the area docs in [`conventions/`](../conventions/).
The `architecture-explainer` subagent grounds its answers here.

AI Daily Summary is a single Python package (`ai_daily`, run as the `ai-daily` CLI) plus a React
dashboard. An ETL pipeline pulls newsletters, feeds and pages into PostgreSQL + pgvector, enriches
each article with Gemini, and scheduled outputs turn the enriched articles into emails, an audio
briefing, a REST API and an MCP server.

## Topology

```
Gmail (whitelist)  RSS feeds  GitHub trending/explore  Web crawlers
        \              |               |                    /
         +-------------+-----ETL pipeline------------------+
                             | extract -> parse -> enrich (Gemini) -> embed -> dedup
                             v
                   PostgreSQL + pgvector
                             |
      +----------+-----------+-----------+-----------+-----------+
      v          v           v           v           v           v
  Newsletter  GitHub     Audio       Release    REST API +   MCP server
  (email +    email      briefing    alerts     dashboard    (tools, via
   radar)                (Pocket TTS)           + chat        REST API)
```

## Components

| Component | Path | Owns | Holds state? |
| :-------- | :--- | :--- | :----------- |
| Extractors | `ai_daily/etl/extractors/` | Fetch raw items per source type (`gmail`, `rss`, `github`, `crawler`); all subclass `BaseExtractor` and yield `RawContent` | no |
| Transformers | `ai_daily/etl/transformers/` | `llm_parser` (split newsletters into items), `embedder` (Gemini embeddings), `deduplicator` (content hash) | no |
| Enrichment | `ai_daily/etl/enrichment.py` | Classify, summarize, tag, detect model releases, embed, semantic dedup | writes `Article` enrichment fields |
| Pipeline | `ai_daily/etl/pipeline.py` | `ETLPipeline`: extract -> transform -> load, then inline enrichment | no |
| Leaderboards | `ai_daily/etl/leaderboards.py` | Capture and diff public model leaderboards | `LeaderboardSnapshot` rows |
| Database | `ai_daily/db/` | SQLAlchemy models (`Source`, `Article`, `DailySummary`, `LeaderboardSnapshot`, `JobRun`), sync + async engines, Alembic migrations | PostgreSQL |
| Outputs | `ai_daily/outputs/` | Newsletter, GitHub email, daily summary, TTS briefing; HTML from `templates/` | `DailySummary` rows, audio files |
| Orchestrator | `ai_daily/orchestrator/` | Cron scheduler, executor with exponential-backoff retries, failure notifier, job registry | `JobRun` rows |
| API | `ai_daily/api/` | FastAPI: REST routes, Gemini function-calling chat, optional bearer-token auth; serves the dashboard | no |
| Dashboard | `frontend/` | React 19 + Vite + Tailwind SPA, built into `ai_daily/static/` (generated, gitignored) | browser localStorage (API token) |
| MCP server | `scripts/aidaily_mcp.py` | Standalone script adapting the REST API into MCP tools | no |
| CLI | `ai_daily/cli.py` | `ai-daily` entrypoint (click + rich) | no |
| Config | `ai_daily/config.py` | Environment-driven config; `config.json` (whitelist, recipients) with `config.example.json` fallback | no |

## Directory layout

```
ai_daily/
  api/            routes.py (REST), chat.py (Gemini function calling), auth.py, server.py
  db/             models, connection, seed.py, migrations/ (Alembic)
  etl/            extractors/, transformers/, enrichment.py, leaderboards.py, pipeline.py, urlcheck.py
  orchestrator/   scheduler, executor, notifier, jobs, types
  outputs/        newsletter, github_newsletter, summary_generator, tts_briefing, html_utils
  static/         built dashboard (generated)
  cli.py, config.py
frontend/         React dashboard source
templates/        HTML email templates
scripts/          aidaily_mcp.py, worktree and pre-commit scripts
tests/            pytest suite (SQLite-backed fixtures)
docs/             conventions/, reference/, explanation/, design/, adr/
```

## Request and data flow

### Path A: scheduled ETL (`etl` job, `0 */4 * * *` UTC)

1. The orchestrator scheduler fires the `etl` job; the executor records a `JobRun` and retries on failure.
2. `ETLPipeline` runs each enabled `Source` through its extractor, producing `RawContent`.
3. Gmail content is filtered by the sender whitelist; newsletters are split into items by `llm_parser`.
4. Items are hashed and exact duplicates skipped, then stored as `Article` rows.
5. Enrichment classifies, summarizes, tags (`model-release`), embeds, and marks semantic duplicates.
6. Newly detected model releases trigger an instant alert email.

### Path B: daily outputs (`newsletter` `0 14 * * *`, `github` `0 10 * * *`, `leaderboards` `0 7 * * *`)

1. The job reads enriched `Article` rows (their `summary`/`category`, never re-derived).
2. `summary_generator` produces a `DailySummary` (with a visible fallback on LLM failure).
3. The TTS briefing is generated and attached; the HTML newsletter (with Release Radar) is sent via the Gmail API to `RECIPIENTS`.
4. Failures retry with backoff; a failure email goes out at most once per job per hour.

### Path C: HTTP API request

1. Request reaches FastAPI (`ai_daily/api/server.py`); CORS applies only when `CORS_ORIGINS` is set.
2. Mutating routes depend on `require_api_token` (skipped when `API_TOKEN` is unset); reads are open.
3. Pydantic models validate input; routes use the DB-session dependency.
4. Source-test requests pass `ensure_public_http_url` before any outbound fetch.
5. Pydantic response models shape the response; the SPA is served for non-API paths.

## External dependencies

| Dependency | Used for | Accessed from | Failure behaviour |
| :--------- | :------- | :------------ | :---------------- |
| PostgreSQL 16 + pgvector | All persistent state, vector search | `ai_daily/db/` | Fail fast; migrations run on container boot |
| Google Gemini (`google-genai`) | Enrichment, parsing, summaries, embeddings, chat | `etl/`, `outputs/`, `api/chat.py` | Per-article errors counted; summary degrades to a visible fallback |
| Gmail API (OAuth) | Read whitelisted newsletters, send all emails | `etl/extractors/gmail.py`, outputs | Job fails and retries; failure email |
| GitHub, RSS feeds, crawled sites | Extra sources | `etl/extractors/` | Per-source errors logged; other sources continue |
| Pocket TTS (optional `tts` extra) | Audio briefing | `outputs/tts_briefing.py` | Newsletter still sent |
| Playwright + Chromium (optional `leaderboards` extra) | Leaderboard capture | `etl/leaderboards.py` | Job fails and retries |

## Deployment topology

Docker Compose runs two services: `postgres` (`pgvector/pgvector:pg16`) and `app`. The app
container runs migrations and seeding, then the orchestrator and the API (uvicorn, port 8000)
side by side; if either dies the container exits and Docker restarts it. Both ports bind to
`127.0.0.1` by default (`API_BIND`, `DB_BIND`). The MCP server runs on the host, outside Docker.
Single instance; no horizontal scaling.
