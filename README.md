# AI Daily Summary

A self-hosted AI news pipeline. It pulls the newsletters you already receive in Gmail, RSS feeds,
GitHub trending and any site you point a crawler at, enriches every article with Google Gemini
(relevance, category, summary, tags, embeddings), stores everything in PostgreSQL + pgvector, and
sends you one daily HTML newsletter with a spoken audio briefing attached. A React dashboard, a
REST API, a chat endpoint over your own data and an MCP server sit on top of the same database.

Bring your own Gmail account, Google AI Studio key and list of newsletter senders.

## Features

- **Gmail newsletter ingestion**: reads recent mail from a whitelist of sender addresses.
- **RSS feeds, GitHub trending/explore and configurable web crawlers** as extra sources.
- **Inline LLM enrichment** during ETL: AI relevance, category, 2-3 sentence summary, tags and
  model-release detection with Gemini; pgvector embeddings; semantic deduplication.
- **Daily HTML newsletter** by email with a "Release Radar" section for new model releases.
- **Separate GitHub hot-repos email.**
- **Spoken audio briefing** generated with Pocket TTS and attached to the newsletter.
- **Instant model-release alerts** emailed as soon as ETL detects a release.
- **Leaderboard watcher**: snapshots public model leaderboards, diffs them, emails changes.
- **Chat endpoint** (Gemini function calling over your articles, releases, leaderboards and jobs).
- **React dashboard** for articles, sources, whitelist, summaries, releases, briefings, jobs, chat.
- **Orchestrator** with cron schedules, exponential-backoff retries and failure emails.
- **MCP server** exposing the API as tools for Claude Code / Claude Desktop.
- **Docker Compose** deployment: Postgres + pgvector, migrations on boot, orchestrator + API.

## How it works

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
  (email +    email      briefing    alerts     dashboard    (tools)
   radar)                (Pocket TTS)           + chat
```

The orchestrator runs four scheduled jobs (cron, UTC):

| Job | Default schedule | What it does |
| :-- | :-- | :-- |
| `etl` | `0 */4 * * *` | Runs all enabled sources with inline enrichment, then emails instant alerts for newly detected model releases |
| `newsletter` | `0 14 * * *` | Generates the audio briefing, then sends the HTML newsletter with the audio attached |
| `github` | `0 10 * * *` | Sends the GitHub hot-repos email |
| `leaderboards` | `0 7 * * *` | Captures leaderboard snapshots, diffs against the previous one, emails changes |

A fifth job, `tts`, is not scheduled. It generates a standalone briefing and emails it; trigger it
manually with the CLI or the API. Failed jobs are retried with exponential backoff and a failure
email goes to `RECIPIENTS` (rate limited to one per job per hour).

## Quick start with Docker

Prerequisites: Docker with Compose, a [Google AI Studio](https://aistudio.google.com/) API key,
and a Google Cloud OAuth client for Gmail (see below). Python 3.12 + [uv](https://docs.astral.sh/uv/)
on the host are needed once, for the Gmail OAuth flow.

```bash
git clone https://github.com/AlexisBalayre/ai-daily-summary.git
cd ai-daily-summary

cp .env.example .env            # fill GOOGLE_API_KEY, GMAIL_*, RECIPIENTS
cp config.example.json config.json   # your newsletter senders, RSS feeds, crawlers

# One-time Gmail OAuth consent on the host: opens a browser, writes token.json
uv sync
uv run ai-daily gmail auth

docker compose up -d --build
open http://localhost:8000
```

On boot the container waits for Postgres, runs `alembic upgrade head`, seeds sources from
`config.json`, starts the orchestrator in the background and serves the API + dashboard on port
8000 (bound to `127.0.0.1` by default). `token.json` and `config.json` are bind-mounted into the
container, so keep both next to `docker-compose.yml` or point `GMAIL_TOKEN_PATH` / `CONFIG_FILE`
at them in `.env`.

To ingest right away instead of waiting for the next cron tick:

```bash
docker compose exec app ai-daily orchestrator trigger etl
```

## Gmail API setup

The app reads newsletters and sends email through one Gmail account, using OAuth 2.0.

1. In Google Cloud Console create a project and enable the **Gmail API**.
2. Configure the OAuth consent screen and add your Gmail address as a test user.
3. Create an OAuth client ID of type **Desktop app**. Copy the client ID, client secret and project
   ID into `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_PROJECT_ID`.
4. The consent flow uses a loopback redirect on `http://localhost:<GMAIL_OAUTH_PORT>/`
   (default port `56450`). Desktop clients accept any loopback port; if you registered explicit
   redirect URIs, they must include that one.
5. Run the flow once on a machine with a browser (command in Quick start). Scopes requested are
   `gmail.readonly` and `gmail.send`. The refresh token is saved to `GMAIL_TOKEN_PATH`
   (default `token.json`) and rotated in place afterwards.

## Personalising it

Everything user-specific lives in `.env` and `config.json`. Both are gitignored.

**Brand and recipients** (`.env`)

- `NEWSLETTER_BRAND` is the name used in email subjects and footers.
- `RECIPIENTS` is a comma-separated fallback list for every email, including failure alerts.
- `NEWSLETTER_RECIPIENTS`, `GITHUB_RECIPIENTS`, `TTS_RECIPIENTS` override it per email type.

**Sources** (`config.json`, copied from `config.example.json`)

- `whitelist`: sender addresses whose mail is ingested as newsletters. Only mail from these
  addresses, received in the last two days, is processed.
- `rss_feeds`: `{name, url}` entries.
- `crawlers`: `{name, url, selectors, content_mode}` entries for sites without a feed.
  `selectors.items` is a CSS selector for each entry; `link`, `title`, `description`, `author`,
  `date` and `content` are selectors relative to it (`@href` reads an attribute).
  `content_mode` is `summary_only` or `fetch_full` (follow each link and extract the article).

Sources are seeded into the database on container start and by every orchestrator ETL run. Seeding is
idempotent by type and name, so adding entries to `config.json` is enough. You can also add,
edit, test, toggle and delete sources from the dashboard (Sources page), the API or
`ai-daily source add-rss`. The GitHub source is created automatically with trending and explore
both enabled.

The whitelist can be edited from the dashboard (Whitelist page) or the `/whitelist` endpoints,
which rewrite `config.json`. The Gmail extractor reads that file on every run, so changes apply
to the next ETL run without reseeding.

**Schedules and retries** (`.env`): `ETL_SCHEDULE`, `NEWSLETTER_SCHEDULE`, `GITHUB_SCHEDULE`,
`LEADERBOARD_SCHEDULE` are cron expressions in UTC. `RETRY_MAX_ATTEMPTS`, `RETRY_BASE_DELAY`,
`RETRY_MULTIPLIER` control retries.

**Audio briefing** (`.env`): `TTS_VOICE` picks the Pocket TTS voice (default `alba`).
Briefings are written to `DATA_DIR/briefings/<date>_briefing.wav` with the script next to them.
Set `TTS_OUTPUT_DIR` to also copy each briefing somewhere else, such as a folder synced to a
phone.

**Models** (`.env`): `LLM_MODEL` (default `gemini-2.0-flash-lite`) is used for enrichment,
summaries, briefing scripts and chat; `EMBEDDING_MODEL` (default `gemini-embedding-001`) for
embeddings at 768 dimensions. Google Gemini via `google-genai` is the only provider implemented;
`LLM_PROVIDER` exists but only `google` is supported.

**Leaderboards**: the tracked boards are a list in `ai_daily/etl/leaderboards.py`
(Artificial Analysis, Arena, Hugging Face Open LLM, Coval). Client-rendered boards need the
Playwright Chromium that the Docker image installs.

## CLI reference

```
ai-daily gmail auth                 One-time Google OAuth consent; writes the token file
ai-daily init                       Create the schema directly (Docker uses Alembic instead)
ai-daily seed                       Seed sources from config.json (or config.example.json)
ai-daily run {gmail|github|crawlers|rss|all}
                                    Run ETL for one source type, or all
ai-daily run-daily                  Same as `orchestrator trigger all` (ETL, newsletter + briefing, GitHub)
ai-daily status                     Job runs from the last 24 hours
ai-daily search <query>             Keyword search over titles and content
ai-daily serve [--host] [--port] [--reload]
                                    API server, 127.0.0.1:8000 by default
ai-daily source list
ai-daily source add {newsletter|github|crawler|rss} <name> [--config '<json>']
ai-daily source add-rss <name> <url>
ai-daily orchestrator start         Run the scheduler in the foreground
ai-daily orchestrator status        Schedules, next runs, recent runs
ai-daily orchestrator trigger {etl|newsletter|github|tts|leaderboards|all}
                                    Run a job now ('all' = etl, newsletter, github in sequence)
```

Run them as `uv run ai-daily ...` locally or `docker compose exec app ai-daily ...` in Docker.

## Dashboard

The React dashboard is built into `ai_daily/static/` and served by the API at `/`. Pages:

| Route | Page |
| :-- | :-- |
| `/` | Dashboard: counts, last job, next scheduled runs |
| `/articles` | Browse and filter articles |
| `/sources` | Add, edit, test, toggle and delete sources |
| `/whitelist` | Newsletter sender whitelist |
| `/summaries` | Daily summaries |
| `/releases` | Release Radar: detected model releases |
| `/leaderboards` | Latest leaderboard snapshots |
| `/briefings` | Play audio briefings and read their scripts |
| `/chat` | Chat with your data |
| `/jobs` | Job history and manual triggers |

## API reference

All routes are under `/api/v1` except `/health`. Interactive docs at `/docs`. There is no
authentication (see Security notes).

| Method | Path | Description |
| :-- | :-- | :-- |
| GET | `/health` | Liveness check |
| GET | `/api/v1/articles` | List articles. Filters: `q`, `topic`, `category`, `is_ai_related`, `is_duplicate`, `source_type`, `exclude_source_type`, `from`, `to`, `limit`, `offset` |
| GET | `/api/v1/articles/{id}` | One article |
| GET | `/api/v1/search?q=` | Semantic search (pgvector cosine), keyword fallback if embedding fails |
| GET | `/api/v1/summaries` | Daily summaries |
| GET | `/api/v1/summary/{YYYY-MM-DD}` | Summary for one day |
| GET | `/api/v1/sources` | List sources |
| GET | `/api/v1/sources/{id}` | One source |
| POST | `/api/v1/sources` | Create a source |
| PUT | `/api/v1/sources/{id}` | Update a source |
| DELETE | `/api/v1/sources/{id}` | Delete a source |
| PATCH | `/api/v1/sources/{id}/toggle` | Enable or disable |
| POST | `/api/v1/sources/test` | Test an RSS, newsletter or crawler config without saving |
| GET | `/api/v1/whitelist` | Sender whitelist |
| POST | `/api/v1/whitelist` | Add a sender (`{"email": "..."}`) |
| DELETE | `/api/v1/whitelist/{email}` | Remove a sender |
| GET | `/api/v1/status` | Counts, last job, next scheduled runs |
| GET | `/api/v1/jobs` | Recent job runs |
| POST | `/api/v1/jobs/{name}/trigger` | Start `etl`, `newsletter`, `github`, `tts` or `leaderboards` in the background |
| GET | `/api/v1/releases?days=7` | Model-release articles from the last N days |
| GET | `/api/v1/leaderboards` | Latest snapshot summary per board |
| GET | `/api/v1/leaderboards/{board}` | Full latest snapshot of one board |
| GET | `/api/v1/briefings` | Generated audio briefings |
| GET | `/api/v1/briefings/{day}/audio` | WAV file for one day |
| GET | `/api/v1/briefings/{day}/script` | Spoken script for one day |
| POST | `/api/v1/chat` | `{"messages": [{"role": "user", "content": "..."}]}` returns a grounded reply and the tools used |

## MCP server

`scripts/aidaily_mcp.py` is a self-contained script (dependencies declared inline) that wraps the
REST API as MCP tools over streamable HTTP. It runs on the host, not in Docker.

```bash
uv run --script scripts/aidaily_mcp.py
# MCP endpoint: http://127.0.0.1:8765/mcp
```

Environment: `AIDAILY_API` (default `http://127.0.0.1:8000/api/v1`), `MCP_PORT` (default
`8765`), `MCP_PUBLIC_HOST` (a public host name to accept, for example a Tailscale DNS name
published with `tailscale serve`; loopback only when unset).

Tools: `search_articles`, `list_articles`, `get_article`, `search_github_repos`,
`latest_releases`, `daily_summary`, `pipeline_status`, `list_sources`, `add_rss_source`,
`toggle_source`, `get_whitelist`, `add_to_whitelist`, `remove_from_whitelist`, `trigger_job`,
`leaderboards`, `leaderboard`.

## Configuration reference

Read from the environment and `.env` by `ai_daily/config.py` unless noted.

| Group | Variable | Default | Notes |
| :-- | :-- | :-- | :-- |
| Database | `DB_HOST` | `localhost` | Compose sets `postgres` inside the container |
| | `DB_PORT` | `5432` | |
| | `DB_BIND` | `127.0.0.1` | Host interface compose publishes Postgres on (compose only) |
| | `DB_NAME` | `ai_daily` | |
| | `DB_USER` | `postgres` | |
| | `DB_PASSWORD` | empty (`postgres` in Compose) | |
| LLM | `GOOGLE_API_KEY` | none | Required. Google AI Studio key |
| | `LLM_PROVIDER` | `google` | Only `google` is implemented |
| | `LLM_MODEL` | `gemini-2.0-flash-lite` | Enrichment, summaries, briefing script, chat |
| | `EMBEDDING_MODEL` | `gemini-embedding-001` | 768-dimension embeddings |
| Gmail | `GMAIL_CLIENT_ID` | none | Required |
| | `GMAIL_CLIENT_SECRET` | none | Required |
| | `GMAIL_PROJECT_ID` | none | Required |
| | `GMAIL_TOKEN_PATH` | `token.json` | Refresh token location; also the Compose mount source |
| | `GMAIL_OAUTH_PORT` | `56450` | Loopback port for the one-time consent flow |
| | `GOOGLE_AUTH_URI`, `GOOGLE_TOKEN_URI`, `GOOGLE_AUTH_PROVIDER_X509_CERT_URL` | Google's standard endpoints | Only override for a custom OAuth setup |
| Email | `NEWSLETTER_BRAND` | `AI Daily` | Subject lines and footers |
| | `RECIPIENTS` | empty | Comma-separated fallback for all emails and failure alerts |
| | `NEWSLETTER_RECIPIENTS` | empty | Overrides `RECIPIENTS` for the newsletter and leaderboard alerts |
| | `GITHUB_RECIPIENTS` | empty | Overrides `RECIPIENTS` for the GitHub email |
| | `TTS_RECIPIENTS` | empty | Overrides `RECIPIENTS` for the standalone `tts` job |
| TTS | `TTS_VOICE` | `alba` | Pocket TTS voice |
| | `TTS_TEMP` | `0.6` | Sampling temperature |
| | `TTS_EOS_THRESHOLD` | `-3.0` | Higher stops sooner |
| | `TTS_NOISE_CLAMP` | unset | Model default when unset |
| | `TTS_FRAMES_AFTER_EOS` | `0` | |
| | `TTS_OUTPUT_DIR` | unset | Optional second copy of each briefing (read in `ai_daily/outputs/tts_briefing.py`) |
| Orchestrator | `ETL_SCHEDULE` | `0 */4 * * *` | Cron, UTC |
| | `NEWSLETTER_SCHEDULE` | `0 14 * * *` | |
| | `GITHUB_SCHEDULE` | `0 10 * * *` | |
| | `LEADERBOARD_SCHEDULE` | `0 7 * * *` | |
| | `RETRY_MAX_ATTEMPTS` | `3` | |
| | `RETRY_BASE_DELAY` | `10.0` | Seconds |
| | `RETRY_MULTIPLIER` | `3.0` | |
| Paths | `DATA_DIR` | `<repo>/data` | Briefings live in `DATA_DIR/briefings` |
| | `LOGS_DIR` | `<repo>/logs` | |
| | `TEMPLATES_DIR` | `<repo>/templates` | Email templates |
| | `CONFIG_FILE` | `<repo>/config.json` | Falls back to `config.example.json`; also the Compose mount source |
| API | `API_TOKEN` | empty | Bearer token required on mutating routes (sources, whitelist, job triggers, chat). Empty disables auth |
| | `CORS_ORIGINS` | empty | Comma-separated browser origins allowed cross-site; the bundled dashboard needs none |
| Compose | `API_BIND` | `127.0.0.1` | Host interface the API port is published on (compose only) |

## Local development

```bash
uv sync --all-extras                     # Python deps incl. pytest, ruff and the optional extras
# Extras: `leaderboards` (Playwright + Chromium) and `tts` (Pocket TTS); plain `uv sync` skips both
docker compose up -d postgres            # Postgres + pgvector on localhost:5432
cp .env.example .env                     # point DB_* at localhost
uv run alembic upgrade head              # migrations live in ai_daily/db/migrations
uv run ai-daily seed
uv run ai-daily run rss                  # or gmail / github / crawlers / all
uv run ai-daily serve --reload           # API on http://127.0.0.1:8000

uv run pytest                            # asyncio_mode=auto; external services are mocked
uv run ruff check . && uv run ruff format --check .

cd frontend && npm install
npm run dev                              # Vite on :5173, proxies /api to :8000
npm run build                            # writes ai_daily/static/ (gitignored)
```

Schema changes: edit `ai_daily/db/models.py`, then
`uv run alembic revision --autogenerate -m "describe change"` and review the generated file.

CI runs on every push and pull request: Ruff lint + format check, pytest, frontend ESLint + build
(`.github/workflows/ci.yml`), and gitleaks secret scanning (`.github/workflows/secret-scan.yml`).

## Project structure

```
ai_daily/
  api/            FastAPI app: routes.py (REST), chat.py (Gemini function calling), server.py
  db/             SQLAlchemy models (Source, Article, DailySummary, LeaderboardSnapshot, JobRun),
                  connection, seed.py, migrations/ (Alembic)
  etl/
    extractors/   gmail, rss, github, crawler (all subclass BaseExtractor)
    transformers/ embedder (Gemini), llm_parser, deduplicator
    enrichment.py Inline classification, summary, tags, release detection, semantic dedup
    leaderboards.py  Leaderboard capture and diff
    pipeline.py   ETLPipeline orchestrating extract -> transform -> load
  orchestrator/   scheduler, executor (retries), notifier (failure emails), jobs (registry)
  outputs/        newsletter, github_newsletter, summary_generator, tts_briefing
  static/         Built dashboard (generated, gitignored)
  cli.py          ai-daily entrypoint
  config.py       Environment-driven configuration
frontend/         React 19 + Vite + Tailwind dashboard
templates/        HTML email templates
scripts/          aidaily_mcp.py (MCP server)
tests/            pytest suite
docs/conventions/ Coding conventions per area; docs/design/ design notes
.claude/          Claude Code agents, rules, hooks and skills for this repo
Dockerfile, docker-compose.yml, docker-entrypoint.sh
```

## Security notes

- **Reads are open; writes are gated by `API_TOKEN`.** Anyone who can reach port 8000 can read
  every article and summary. Set `API_TOKEN` before exposing the port: sources, whitelist, job
  triggers and chat then require `Authorization: Bearer <token>` (the dashboard asks for it once
  and keeps it in the browser's localStorage). Compose binds the API and Postgres to `127.0.0.1`;
  only change `API_BIND`/`DB_BIND` behind an authenticating reverse proxy or a private network
  such as Tailscale.
- Cross-origin browser access is off unless `CORS_ORIGINS` lists the origins. The source-test
  endpoint only fetches public http(s) hosts, so it cannot be used to probe your network.
- The MCP server is unauthenticated too and listens on loopback. `MCP_PUBLIC_HOST` is meant for a
  Tailscale-published name, not the public internet.
- `.env`, `token.json` and `config.json` hold your API key, a Gmail refresh token with send
  permission, and your sender list. They are gitignored; never commit them. `token.json` is
  written with mode 0600. Gitleaks runs in CI as a
  backstop. If the token leaks, revoke the app from your Google account.
- Crawled pages and whitelisted newsletters are untrusted input that is fed to the LLM.

## Contributing

- Branch off `master` and open a pull request; nothing is committed to `master` directly.
- CI must pass: Ruff, pytest, frontend lint and build, secret scan.
- Follow the per-area conventions in `docs/conventions/`. Highlights: timezone-aware datetimes,
  `logging` not `print`, outputs consume enriched fields rather than re-deriving them.
- `.claude/` and `CLAUDE.md` ship a Claude Code setup (agents, path-scoped rules, hooks, skills)
  that encodes the same conventions.

## License

MIT. See `LICENSE`.
