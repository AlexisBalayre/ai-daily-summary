# Contributing

Thanks for taking the time. This is a small project, so the process is light.

## Setup

```bash
uv sync --all-extras
docker compose up -d postgres
uv run alembic upgrade head
uv run pytest
cd frontend && npm install && npm run dev
```

## Making a change

1. Branch off `master`. Never commit to `master` directly.
2. Follow the conventions in `docs/conventions/` (the rules that bite most: `logging` not
   `print`, timezone-aware datetimes, HTML-escape anything that reaches an email).
3. Add or update tests under `tests/`. They run offline against SQLite; mock every external
   service.
4. Run `uv run ruff check . && uv run ruff format . && uv run pytest` before pushing. CI runs
   the same plus the frontend lint and build, and gitleaks.
5. If you touch `ai_daily/db/models.py`, generate a migration with
   `uv run alembic revision --autogenerate -m "..."` and check the result by hand.
6. Open a pull request against `master` with a short description of what changed and why.

## Reporting a security issue

Do not open a public issue for a vulnerability. Email the maintainer listed in `pyproject.toml`
or use GitHub's private vulnerability reporting on the repository.

## Claude Code

The repository ships a Claude Code configuration under `.claude/` (hooks, rules, agents, skills)
and a `CLAUDE.md`. It is optional; nothing in the build depends on it.
