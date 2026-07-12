---
paths:
  - "**/*.py"
---

# Universal Python Conventions — Quick Reference

**CRITICAL:** These rules apply to EVERY Python file. See `@docs/conventions/general.md` for the full doc.

## Naming

- **Modules & packages:** `snake_case.py` (enforced by `.claude/hooks/validate-file-naming.sh`). No hyphens, no camelCase, no PascalCase.
- **Classes:** `PascalCase`. **Functions / variables:** `snake_case`. **Constants:** `UPPER_SNAKE`.
- Booleans read as predicates: `is_`, `has_`, `should_`.

## Formatting & Linting

Ruff is the single source of truth (lint + format), run automatically on the `Stop` hook against the files this session touched. Don't run it manually and don't hand-format — let `ruff format` win. Line length and rule set live in `[tool.ruff]` in `pyproject.toml`.

## Imports

- **No wildcard imports** (`from x import *`).
- Standard lib → third-party → first-party (`ai_daily.*`), each group separated; Ruff's isort ordering enforces this.
- Import names explicitly; prefer module-qualified access for clarity in large modules.

## Type Hints

- Public functions and methods are fully annotated (params + return).
- Prefer `X | None` over `Optional[X]` (3.12 target). Use `list[str]`, `dict[str, int]` — not `List`/`Dict`.
- Avoid bare `Any` outside true boundaries; annotate a justification when unavoidable.

## Datetimes

- **Never `datetime.utcnow()`** — deprecated in 3.12 and returns a *naive* datetime. Use `datetime.now(timezone.utc)`.
- Keep DB-stored timestamps timezone-aware and compare consistently.

## Errors & Logging

- **Never bare `except:`** — catch `Exception` or narrower; log with the module logger and re-raise or handle deliberately. No silent `pass`.
- **Use `logging`, not `print()`**, in library code (`ai_daily/**`). The CLI (`ai_daily/cli.py`) may use `rich`/`click` output.
- One `logger = logging.getLogger(__name__)` per module.

## Comments & Clean Code

- Comments explain WHY, never WHAT. If deleting the comment wouldn't confuse a reader, delete it. No `# === Section ===` banners, no changelog/journal comments, no commented-out code.
- DELETE old code when replacing — no shims, no "removed" markers, no backwards-compat re-exports.
- YAGNI: don't build for hypothetical requirements. Pull ports/URLs/model names/timeouts from `ai_daily/config.py` or `.env`, never inline them.
