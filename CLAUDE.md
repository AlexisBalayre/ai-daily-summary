@AGENTS.md

## Claude Code specifics

- `docs/conventions/*.md` reach you through `.claude/rules/`: the first Read, Edit, or Write of a file in an area injects that area's doc for the rest of the session. Never Read a conventions doc yourself; that duplicates tokens already in context.
- MCP results (codegraph) do not fire rules. Before your first edit in an area, Read one existing file there with the Read tool; the "read 2-3 similar files" rule already asks for this.
- Hooks enforce the workflow: `git-safety` blocks trunk commits, force-push, `reset --hard`, `rm -rf`, `DROP TABLE`; `protect-generated` blocks edits to `ai_daily/static/`, `uv.lock`, `*.pyc`; the `Stop` hook runs Ruff on the files the session touched.

## Subagents (invoke proactively via Agent tool)

- `convention-checker` — before commit, or after ≥3 files changed across `ai_daily/`.
- `migration-reviewer` — after editing `ai_daily/db/models.py` or generating an Alembic migration.
- `security-reviewer` — after editing API routes, Gmail/OAuth handling, the crawler, HTML email generation, or anything touching `.env`/`token.json`.
- `architecture-explainer` — for *why*/*how* questions about the ETL → enrichment → outputs flow.

The `review-*` agents (correctness, security, conventions, context, maintainability, docs, validator) are
not invoked directly; the `/pr-ci-review` skill dispatches them.
