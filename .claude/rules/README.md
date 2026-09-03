# Rule catalog

Path-scoped convention rules. Each auto-loads when you open or edit a file matching its `paths:`
frontmatter — you never invoke them. A rule is a thin trigger that imports the full convention
doc (the "split pattern"), so always-on context stays small while full detail loads on demand.

| Rule | Auto-loads for | Enforces (full doc) |
| :--- | :------------- | :------------------ |
| `universal-conventions` | every `**/*.py` | snake_case, logging-not-print, type hints, timezone-aware datetimes, comment discipline → `general.md` |
| `etl-conventions` | `ai_daily/etl/**` | `BaseExtractor` subclasses, `RawContent`, transformer/enrichment pipeline → `etl.md` |
| `api-conventions` | `ai_daily/api/**` | FastAPI routers, Pydantic response models, DB-session dependency, no business logic in routes → `api.md` |
| `database-conventions` | `ai_daily/db/**` (incl. `ai_daily/db/migrations/**`) | SQLAlchemy 2.0 models, pgvector columns, Alembic migration safety → `database.md` |
| `outputs-conventions` | `ai_daily/outputs/**` | Newsletter/TTS generation: use enriched summaries + categories, escape HTML, template loading → `outputs.md` |
| `orchestrator-conventions` | `ai_daily/orchestrator/**` | Cron scheduling, idempotent jobs, retries + failure notifications → `orchestrator.md` |
| `testing-conventions` | `tests/**`, `**/test_*.py` | pytest-asyncio, mock external services, conftest fixtures, behaviour-not-internals → `testing.md` |
| `frontend-conventions` | `frontend/**` | React + Tailwind dashboard, build to `ai_daily/static/` → `frontend.md` |

**How to use:** just edit files in a matching path; the rule and its `docs/conventions/*.md`
import load automatically. To add a rule, see [`.claude/README.md`](../README.md) ("New rule").
