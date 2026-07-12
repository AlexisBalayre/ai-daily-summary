#!/bin/bash
# Quality checks: ruff lint + format on the session's dirty Python files.
# Runs on Claude Code Stop event — after every response that modifies files.
# Tests are NOT run here (too slow for every turn; run `uv run pytest` explicitly).
# Whole-repo lint is deliberately avoided so unrelated red on master can't block
# an unrelated session — only files this session touched are checked.

set -o pipefail

cd "$CLAUDE_PROJECT_DIR" || exit 1

# uv lives in ~/.local/bin, which isn't on the non-interactive PATH.
export PATH="$HOME/.local/bin:$PATH"

# Only .py files trigger the suite; markdown/YAML/JSON/HTML edits skip it.
# Includes untracked files (Write-created files aren't staged yet).
DIRTY_PY=$(
  {
    git diff --name-only 2>/dev/null
    git diff --cached --name-only 2>/dev/null
    git ls-files --others --exclude-standard 2>/dev/null
  } | grep -E '\.py$' | sort -u | while read -r f; do [ -f "$f" ] && echo "$f"; done
)

if [ -z "$DIRTY_PY" ]; then
  exit 0
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "quality-checks: uv not found on PATH; skipping ruff." >&2
  exit 0
fi

echo "Running quality checks..." >&2

# 1. Auto-fix lint issues + format the dirty files only.
echo "-> Ruff lint (auto-fix) + format on dirty files..." >&2
echo "$DIRTY_PY" | xargs uv run ruff check --fix 1>&2 2>&1
echo "$DIRTY_PY" | xargs uv run ruff format 1>&2 2>&1

# 2. Verify no lint issues remain after auto-fix.
echo "-> Verifying lint..." >&2
if ! echo "$DIRTY_PY" | xargs uv run ruff check 1>&2; then
  echo "Ruff found issues it could not auto-fix on the files this session touched. Fix them above." >&2
  exit 2
fi

echo "All quality checks passed!" >&2
exit 0
