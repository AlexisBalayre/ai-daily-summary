# Core Conventions

Universal rules for every Python file. Area docs in this folder inherit from here; they never relax these rules.

**Genre contract:** obligations only (rules, gotchas, decision rules, naming). System description lives in `docs/reference/`.

## Altitude / YAGNI

Build the smallest thing that meets the requirement. Prefer a deep module (simple surface, logic hidden) over several shallow ones; a module too thin to justify its file gets folded into its caller.

- **Inline by default.** No new file, helper, wrapper, param, option, interface, or generic with a single caller, unless a second caller exists today or a convention in this folder prescribes the construct. A one-call `format_x` helper or one-field `options` object is the bloat this targets.
- **No unreachable defensiveness.** No guard, `except`, or fallback for a state the types or surrounding code already guarantee. Test: if you cannot write the input that reaches the branch, delete it. Real error handling at seams (I/O, external calls, user input) is exempt.
- **Delete when replacing.** No shims, no "removed" markers, no backwards-compat re-exports.

## Comments

Default to no inline comment. A comment explains **WHY** (invariant, unit, ordering, gotcha), never WHAT. A comment whose removal wouldn't confuse a future reader should not exist.

```
retries += 1  # increment the retry counter           (BAD: restates the code)
retries += 1  # 429s are transient, so retry first    (GOOD: explains the why)
```

**Seam-duplication test:** a call-site WHY comment that restates the callee's docstring is a duplicate; the explanation lives at the seam. Before keeping a comment that explains another module's behaviour, read that module's docs; if they already say it, delete the call-site copy.

Docstrings: an imperative one-line summary (`"""Process unenriched articles."""`) is the contract. Never paraphrase the symbol name or a parameter's type; no file-header banners, `# === Section ===` dividers, changelog comments, or commented-out code. The `comment-pruner` hook flags net-new violations.

This section is deliberately mirrored in `AGENTS.md`; keep both in sync.

## Language and types

- Python `>=3.12`. Use modern syntax: `X | None`, built-in generics (`list`, `dict`), structural pattern matching where it reads well, `pathlib.Path` over `os.path`.
- Fully annotate public functions and methods (params + return).
- `Any` only at real boundaries (untyped third-party payloads), with a one-line justification.

## Datetimes

- **`datetime.utcnow()` is banned**: deprecated in 3.12 and returns a naive datetime that silently mismatches the timezone-aware values the DB stores. Use `datetime.now(UTC)` (`from datetime import UTC`; Ruff's pyupgrade rewrites `timezone.utc` to it).
- Store and compare timestamps timezone-aware; the DB layer (`DateTime(timezone=True)`) is the reference.

## Errors

- Never bare `except:` and never swallow: catch `Exception` or narrower, log context, then handle or re-raise. A silent `except ...: pass` hides real failures.
- Degrade *visibly*: when an LLM or external call fails, record a fallback the reader can see (see `_create_fallback_summary` in `ai_daily/outputs/summary_generator.py`) rather than dropping content.

## Logging

- `logger = logging.getLogger(__name__)` at module top; log with it. No `print()` in `ai_daily/**` (`ai_daily/cli.py` uses `rich`/`click` for user-facing output; that's fine).
- Never log secrets or PII: API keys, OAuth tokens, `API_TOKEN`, email bodies, recipient addresses.

## Structure

- **No hardcoded values**: ports, URLs, model names, timeouts, whitelists and recipient lists come from `ai_daily/config.py` (env-overridable) or `config.json` / `.env`, never literals in logic.
- Imports at module top level, except where a lazy import genuinely breaks a cycle (comment why). No wildcard imports.

## Naming

| Kind | Convention | Example |
| :--- | :--------- | :------ |
| Module / package | `snake_case` (enforced by `validate-file-naming.sh`) | `gmail_extractor.py` |
| Class | `PascalCase` | `NewsletterOutput` |
| Function / method / var | `snake_case` | `get_recent_articles` |
| Constant | `UPPER_SNAKE` | `SYSTEM_PROMPT` |
| Boolean | predicate prefix | `is_ai_related`, `has_new_articles_since` |

## Formatting and linting

Ruff owns lint and format (`[tool.ruff]` in `pyproject.toml`). If it reports an error it can't auto-fix, fix the code; don't silence the rule.
