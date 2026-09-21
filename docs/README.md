# Docs

Documentation for this project, organised with [Diátaxis](https://diataxis.fr/):

| Folder              | Answers                | Read when…                                  |
| :------------------ | :--------------------- | :------------------------------------------ |
| `conventions/`      | *How must I code this?* | You're editing files in an area (auto-loaded by `.claude/rules/`). |
| `reference/`        | *What is the shape?*    | You need the structure of a component or data flow. |
| `explanation/`      | *Why is it like this?*  | You're questioning a design decision.       |
| `adr/`              | *What did we decide?*   | You need the record of a past decision.     |
| `design/`           | *How was it planned?*   | You need the dated design note behind a component (pre-ADR records). |
| `research/`         | *What do the sources say?* | You need findings the `research` skill captured (created on first use). |

`conventions/` is the **single source of truth** for code style; conventions files contain
obligations only, while system description lives in `reference/`. Unfamiliar term? See the
[Glossary](glossary.md).

## Conventions index

Per-area rules. Read the one for the area you are changing.

- [core](conventions/core.md) — every Python file: altitude/YAGNI, comments, types, datetimes, errors, logging, structure, naming
- [testing](conventions/testing.md) — `tests/`: pytest-asyncio, mocking external services, fixtures
- [etl](conventions/etl.md) — `ai_daily/etl/`: `BaseExtractor`, `RawContent`, transformers, enrichment
- [api](conventions/api.md) — `ai_daily/api/`: thin FastAPI routers, Pydantic models, session dependency
- [database](conventions/database.md) — `ai_daily/db/`: SQLAlchemy 2.0 models, pgvector, Alembic migration safety
- [outputs](conventions/outputs.md) — `ai_daily/outputs/`: enriched summaries/categories, HTML escaping, templates
- [orchestrator](conventions/orchestrator.md) — `ai_daily/orchestrator/`: idempotent jobs, retries, failure notifications
- [frontend](conventions/frontend.md) — `frontend/`: React + Tailwind, build to `ai_daily/static/`

Each has a matching `.claude/rules/<area>-conventions.md` loader.

## Reference and explanation

- [reference/architecture.md](reference/architecture.md) — components, layout, request/data flow, external dependencies, deployment
- [explanation/security-model.md](explanation/security-model.md) — trust boundaries, authn/authz, secrets, input validation (the `security-reviewer` spec)
- [adr/](adr/README.md) — how to record a decision, plus the template
- [design/](design/) — dated design notes: data platform, orchestrator, article enrichment, frontend dashboard, RSS extractor
- [glossary.md](glossary.md) — shared vocabulary
