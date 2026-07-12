# Database Conventions (`ai_daily/db/`, `alembic/`)

PostgreSQL + pgvector, SQLAlchemy 2.0 (async), Alembic migrations.

## Models (`ai_daily/db/models.py`)

- Core tables: `sources`, `articles`, `daily_summaries`, `job_runs`. Match the existing declarative
  style; don't mix in legacy `Base.query`.
- Use SQLAlchemy 2.0 typed mappings and `select(...)` queries. Prefer `session.execute(select(...))`
  + `.scalars()` over the legacy `Query` API.
- `articles` carries the 768-dim pgvector `embedding` plus enrichment fields (`summary`, `category`,
  `is_ai_related`, `is_duplicate`). If an output needs a value, it should be a column here, computed at
  enrichment time — not recomputed downstream.
- Columns are `snake_case`. Timestamps are timezone-aware (see general.md — no `utcnow()`).

## Migrations (Alembic)

- **Every model change needs a migration.** Generate with `uv run alembic revision --autogenerate -m "…"`,
  then **read and hand-edit** the generated script — autogenerate misses pgvector types, indexes, server
  defaults, and data backfills.
- Migrations must be reversible where feasible (`downgrade` implemented) and safe on a populated table:
  add nullable-or-defaulted columns, create indexes concurrently for large tables, avoid destructive
  drops without an explicit backfill/verify step.
- Never edit an already-applied migration; add a new one.
- Apply with `uv run alembic upgrade head`.

## Queries

- Push filtering to SQL, not Python. Existing filters (`is_ai_related == True`, `is_duplicate == False`,
  time windows on `ingested_at`) belong in the `select`.
- Use pgvector operators for semantic search rather than pulling rows into Python to compare.
