# General Python Conventions

The single source of truth for project-wide Python style. The quick-reference lives in
`.claude/rules/universal-conventions.md`; this is the full doc.

## Language target

Python `>=3.12`. Use modern syntax: `X | None`, built-in generics (`list`, `dict`), structural
pattern matching where it reads well, `pathlib.Path` over `os.path`.

## Naming

| Kind | Convention | Example |
| :--- | :--------- | :------ |
| Module / package | `snake_case` | `gmail_extractor.py` |
| Class | `PascalCase` | `NewsletterOutput` |
| Function / method / var | `snake_case` | `get_recent_articles` |
| Constant | `UPPER_SNAKE` | `SYSTEM_PROMPT` |
| Boolean | predicate prefix | `is_ai_related`, `has_new_articles_since` |

## Formatting & linting

- **Ruff** owns both lint and format. Config is in `pyproject.toml` (`[tool.ruff]`). It runs on the
  `Stop` hook against files the session touched — never hand-format, never run it in a loop.
- If the hook reports an error Ruff can't auto-fix, fix the code, don't silence the rule.

## Imports

- No wildcard imports.
- Grouped stdlib → third-party → first-party (`ai_daily.*`); Ruff's isort enforces order.
- Keep imports at module top level except where a lazy import genuinely breaks a cycle (comment why).

## Type hints

- Fully annotate public functions/methods (params + return).
- `X | None`, not `Optional[X]`. `list[str]`, not `typing.List[str]`.
- `Any` only at real boundaries (untyped third-party payloads); add a one-line justification.

## Datetimes

- **`datetime.utcnow()` is banned** — deprecated in 3.12 and returns a naive datetime that silently
  mismatches timezone-aware values. Use `datetime.now(timezone.utc)`.
- Store and compare timestamps consistently (the DB layer is the reference).

## Errors & logging

- `logger = logging.getLogger(__name__)` at module top; log with it, don't `print()` in `ai_daily/**`.
  (`ai_daily/cli.py` uses `rich`/`click` for user-facing output — that's fine.)
- Never `except:` bare and never swallow: catch `Exception` or narrower, log context, then handle or
  re-raise. A silent `except ...: pass` hides real failures — see the newsletter/summary fallback
  pattern (`_create_fallback_summary`) for how to degrade *visibly*.

## Config, not constants

Ports, URLs, model names, timeouts, whitelists, recipient lists → `ai_daily/config.py` (env-overridable)
or `config.json` / `.env`. Never inline them in logic.

## Comments & clean code

- Comments explain WHY. Delete comments that restate the code. No banner comments, no changelog
  comments, no commented-out code (the `comment-pruner` hook will flag net-new ones).
- Replace, don't accrete: delete superseded code rather than leaving compat shims.
