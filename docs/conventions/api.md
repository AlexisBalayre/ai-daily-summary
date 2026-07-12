# API Conventions (`ai_daily/api/`)

FastAPI server exposing articles, sources, summaries, search, and whitelist management. Serves the
built React dashboard from `ai_daily/static/`.

## Structure

- Group endpoints into routers by resource (articles, sources, summaries, whitelist). Register routers
  on the app; keep `main`/app-setup thin.
- **Routes are thin.** A route validates input, calls into a service/output/db function, and shapes the
  response. Business logic (LLM calls, ETL, newsletter assembly) lives in `ai_daily/etl`, `outputs`, or
  `db` — never inline in a route handler.

## Request / response models

- Use Pydantic models for request bodies and response shapes; never return raw ORM objects or ad-hoc
  dicts. Declare `response_model=` on endpoints.
- Keep API schemas separate from SQLAlchemy models — don't leak DB columns you don't mean to expose.

## Database access

- Get the session via a FastAPI dependency, not a module-global. One session per request; let the
  dependency handle open/close.
- Queries use SQLAlchemy 2.0 `select(...)` style (see `db` conventions), not legacy `Query`.

## Async

Endpoints doing I/O are `async def`. Don't block the event loop with sync DB drivers or `requests` in a
request path — use the async session / `aiohttp`.

## Errors

Raise `HTTPException` with a correct status code for client-visible failures; log server-side detail.
Don't return `200` with an error body.
