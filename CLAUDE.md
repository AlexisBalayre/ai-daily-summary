# AI Daily Summary

AI-powered news aggregation + newsletter platform. Collects content from Gmail newsletters, GitHub
trending, RSS feeds, and web crawlers; enriches it with Google Gemini and pgvector
embeddings; and produces a daily email newsletter, an audio briefing, and a REST API + React dashboard.

## Role

Expert Python architect working in a strict-convention `uv` project (Python 3.12, FastAPI, SQLAlchemy
2.0 async, PostgreSQL + pgvector, Alembic, pytest-asyncio) with a React + Tailwind frontend.

**Core rule:** Before creating or modifying code, read 2-3 similar files in the same package and match
their patterns exactly.

## Module map

| Path | What it is |
| :--- | :--------- |
| `ai_daily/etl/extractors/` | Source extractors (`gmail`, `rss`, `github`, `crawler`), all subclass `BaseExtractor` |
| `ai_daily/etl/transformers/` | `embedder` (Gemini), `llm_parser`, `deduplicator` |
| `ai_daily/etl/enrichment.py` | Inline enrichment during ETL: classify, summarize, semantic dedup |
| `ai_daily/db/` | SQLAlchemy models (`Source`, `Article`, `DailySummary`, `JobRun`) + pgvector |
| `ai_daily/outputs/` | Newsletter, GitHub email, daily summary, TTS briefing generation |
| `ai_daily/api/` | FastAPI server (articles, sources, summaries, search, whitelist); serves the dashboard |
| `ai_daily/orchestrator/` | Cron-scheduled jobs with retries + failure notifications |
| `ai_daily/cli.py` | `ai-daily` CLI entrypoint (click + rich) |
| `frontend/` | React + Tailwind dashboard; builds to `ai_daily/static/` |
| `ai_daily/db/migrations/` | Alembic migrations (`env.py` + `versions/`) |

## Conventions

Path-scoped rules in `.claude/rules/*.md` auto-load the matching `docs/conventions/<area>.md` when you
touch a file in that area. `docs/conventions/` is the single source of truth. Highlights that bite
often here: use `logging` not `print`, **never `datetime.utcnow()`** (use `datetime.now(timezone.utc)`),
and in `outputs/` consume the enriched `summary`/`category` fields rather than re-deriving them.

## Git workflow (CRITICAL)

- Trunk is `master`. **NEVER commit or push to `master`.** Feature branches / PRs only.
- Use a worktree per task: `git worktree add .worktrees/<name> -b feat/<name>`. NEVER `git checkout -b`
  in the main worktree. (`.worktrees/` is git-ignored.)
- `git branch --show-current` MUST NOT be `master` before committing. The `git-safety` hook enforces
  this and blocks force-push / `reset --hard` / `rm -rf` / `DROP TABLE`.

## Key commands

| Command | Purpose |
| :------ | :------ |
| `uv sync` | Install dependencies (incl. dev: pytest, ruff) |
| `uv run ai-daily serve` | Start API server (port 8000) |
| `uv run ai-daily run all` | Full ETL pipeline (all sources + inline enrichment) |
| `uv run ai-daily run gmail\|rss\|github` | Single-source ETL |
| `uv run ai-daily orchestrator start\|status\|trigger etl` | Scheduled jobs |
| `uv run pytest` | Run tests (`asyncio_mode=auto`) |
| `uv run alembic revision --autogenerate -m "…"` / `upgrade head` | Migrations |
| `cd frontend && npm install && npm run build` | Build the dashboard into `ai_daily/static/` |

**Linting/formatting:** Ruff runs automatically on the `Stop` hook against the files a session touched.
Don't run it manually or hand-format.

## Subagents (invoke proactively via Agent tool)

- `convention-checker` — before commit, or after ≥3 files changed across `ai_daily/`.
- `migration-reviewer` — after editing `ai_daily/db/models.py` or generating an Alembic migration.
- `security-reviewer` — after editing API routes, Gmail/OAuth handling, or anything touching `.env`/`token.json`.
- `architecture-explainer` — for *why*/*how* questions about the ETL → enrichment → outputs flow.

The `review-*` agents (correctness, security, conventions, context, maintainability, docs, validator) are
not invoked directly; the `/pr-ci-review` skill dispatches them.
