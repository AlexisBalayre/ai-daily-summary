# Rule catalog

Path-scoped convention rules. Each auto-loads when you open or edit a file matching its `paths:`
frontmatter — you never invoke them. A rule is a **pure loader**: `paths:` frontmatter plus a
single `@docs/conventions/<area>.md` import, no content of its own. `docs/conventions/` is the
single source of truth, so always-on context stays small while full detail loads on demand.

| Rule | Auto-loads for | Enforces (full doc) |
| :--- | :------------- | :------------------ |
| `core-conventions` | every `**/*.py` | Altitude/YAGNI, comments, types, no `utcnow()`, logging-not-print, errors, config-not-constants, snake_case naming → `core.md` |
| `etl-conventions` | `ai_daily/etl/**` | `BaseExtractor` subclasses, `RawContent`, transformer/enrichment pipeline → `etl.md` |
| `api-conventions` | `ai_daily/api/**` | FastAPI routers, Pydantic response models, DB-session dependency, no business logic in routes → `api.md` |
| `database-conventions` | `ai_daily/db/**` (incl. `ai_daily/db/migrations/**`) | SQLAlchemy 2.0 models, pgvector columns, Alembic migration safety → `database.md` |
| `outputs-conventions` | `ai_daily/outputs/**` | Newsletter/TTS generation: use enriched summaries + categories, escape HTML, template loading → `outputs.md` |
| `orchestrator-conventions` | `ai_daily/orchestrator/**` | Cron scheduling, idempotent jobs, retries + failure notifications → `orchestrator.md` |
| `testing-conventions` | `tests/**/*.py`, `**/test_*.py` | pytest-asyncio, mock external services, conftest fixtures, behaviour-not-internals → `testing.md` |
| `frontend-conventions` | `frontend/**` | React + Tailwind dashboard, build to `ai_daily/static/` → `frontend.md` |

**How to use:** just edit files in a matching path; the rule and its `docs/conventions/*.md`
import load automatically. To add a rule, see [`.claude/README.md`](../README.md) ("New rule").
