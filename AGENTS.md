# AI Daily Summary

AI-powered news aggregation + newsletter platform. Collects content from Gmail newsletters, GitHub
trending, RSS feeds, and web crawlers; enriches it with Google Gemini and pgvector embeddings; and
produces a daily email newsletter, an audio briefing, and a REST API + React dashboard. A single
`uv` Python package (`ai_daily`) plus a React frontend in `frontend/`.

Instructions for AI coding agents, whatever the tool. Tool-specific layers build on this file: Claude Code adds `CLAUDE.md` and `.claude/`, Cursor adds `.cursor/`.

## Role

Expert Python architect working in a strict-convention `uv` project (Python 3.12, FastAPI, SQLAlchemy
2.0 with sync and async sessions, PostgreSQL + pgvector, Alembic, pytest-asyncio) with a React +
Tailwind frontend.

**Core rule:** Before creating or modifying code, read 2-3 similar files in the same package and match their patterns exactly.

## Conventions

`docs/conventions/` is the single source of truth. The conventions for every area covering a file must be in context before you touch it: Claude Code injects them through `.claude/rules/`; other tools read them from this table.

| Area | Paths | Conventions |
| --- | --- | --- |
| Core | any `*.py` file | `docs/conventions/core.md` |
| Testing | `tests/**/*.py`, `**/test_*.py` | `docs/conventions/testing.md` |
| ETL | `ai_daily/etl/**` | `docs/conventions/etl.md` |
| API | `ai_daily/api/**` | `docs/conventions/api.md` |
| Database | `ai_daily/db/**` (incl. `migrations/`) | `docs/conventions/database.md` |
| Outputs | `ai_daily/outputs/**` | `docs/conventions/outputs.md` |
| Orchestrator | `ai_daily/orchestrator/**` | `docs/conventions/orchestrator.md` |
| Frontend | `frontend/**` | `docs/conventions/frontend.md` |

Highlights that bite often here: use `logging` not `print`, **never `datetime.utcnow()`** (use
`datetime.now(UTC)`), and in `outputs/` consume the enriched `summary`/`category` fields rather than
re-deriving them.

`docs/README.md` (Diátaxis-structured) covers anything outside these areas; shared vocabulary lives in `docs/glossary.md`.

## Layout

Topology, components and data flow: `docs/reference/architecture.md`. Trust boundaries and secrets: `docs/explanation/security-model.md`. Dated design notes: `docs/design/`.

| Path | What it is |
| :--- | :--------- |
| `ai_daily/etl/extractors/` | Source extractors (`gmail`, `rss`, `github`, `crawler`), all subclass `BaseExtractor` |
| `ai_daily/etl/transformers/` | `embedder` (Gemini), `llm_parser`, `deduplicator` |
| `ai_daily/etl/enrichment.py` | Inline enrichment during ETL: classify, summarize, semantic dedup |
| `ai_daily/db/` | SQLAlchemy models (`Source`, `Article`, `DailySummary`, `LeaderboardSnapshot`, `JobRun`) + pgvector |
| `ai_daily/db/migrations/` | Alembic migrations (`env.py` + `versions/`) |
| `ai_daily/outputs/` | Newsletter, GitHub email, daily summary, TTS briefing generation |
| `ai_daily/api/` | FastAPI server (articles, sources, summaries, search, whitelist, chat); serves the dashboard |
| `ai_daily/orchestrator/` | Cron-scheduled jobs with retries + failure notifications |
| `ai_daily/cli.py` | `ai-daily` CLI entrypoint (click + rich) |
| `frontend/` | React + Tailwind dashboard; builds to `ai_daily/static/` (generated, never hand-edit) |
| `scripts/aidaily_mcp.py` | MCP server adapting the REST API |

## Comments

Default to no inline comment. Add one only for a non-obvious WHY (invariant, unit, ordering, gotcha), never to narrate WHAT the code does. If removing a comment wouldn't confuse a competent reader, delete it. A WHY comment that restates the callee's doc comment is a duplicate: read the callee's docs before keeping it; if the seam already says it, delete the call-site copy.

```
retries += 1  # increment the retry counter           (BAD: restates the code)
retries += 1  # 429s are transient, so retry first    (GOOD: explains the why)
```

## Altitude

Build the smallest thing that works; the obligation lives in `docs/conventions/core.md` §Altitude / YAGNI. Before finishing a change that introduced any discretionary construct (new file, helper, wrapper, option, param, interface, generic, or defensive branch), list each one with a keep-or-inline verdict; keep means you can name a second caller or a real WHY. Default to inline/delete. Don't list constructs a convention prescribes, and skip the audit silently when a change added none. Unjustifiable bloat is a `/simplify` candidate.

## Git workflow (CRITICAL)

- Trunk is `master` (`GIT_TRUNK` in `.claude/project.env`). **NEVER commit or push to `master`.** PRs only.
- ALWAYS use `scripts/worktree-create.sh <name>` (creates `.worktrees/<name>` on `feat/<name>` and runs `uv sync`). NEVER `git checkout -b` in the main worktree. (`.worktrees/` is git-ignored.)
- `git branch --show-current` MUST NOT be `master` before committing.
- `scripts/worktree-clean.sh` removes worktrees whose remote branch is gone.

## Key commands

Lint, test and install commands live in `.claude/project.env` (`LINT_CMD`, `TEST_CMD`, `INSTALL_CMD`).

| Command | Purpose |
| :------ | :------ |
| `uv sync` | Install dependencies (incl. dev: pytest, ruff). Extras `leaderboards` (Playwright) and `tts` (Pocket TTS) are opt-in |
| `uv run ai-daily serve` | Start API server (port 8000, binds `127.0.0.1`) |
| `uv run ai-daily run all` | Full ETL pipeline (all sources + inline enrichment) |
| `uv run ai-daily run gmail\|rss\|github` | Single-source ETL |
| `uv run ai-daily orchestrator start\|status\|trigger etl` | Scheduled jobs |
| `uv run pytest` | Run tests (`asyncio_mode=auto`; SQLite fixtures, no Postgres needed) |
| `uv run alembic revision --autogenerate -m "…"` / `upgrade head` | Migrations (need Postgres up, e.g. `docker compose up postgres`) |
| `cd frontend && npm install && npm run build` | Build the dashboard into `ai_daily/static/` |

Gotchas: ETL and outputs need `.env` (`GOOGLE_API_KEY`, DB settings) and a Gmail `token.json` from `ai-daily gmail auth`; never read or commit either. Ruff 0.16 also formats Python code blocks inside Markdown, so `ruff format --check` covers docs too.

**Formatting/linting:** run Ruff (`uv run ruff check --fix` + `uv run ruff format`) on the files you touched before handing work back. (Claude Code only: don't run it manually; its `Stop` hook runs it automatically.)
