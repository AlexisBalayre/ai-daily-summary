#!/usr/bin/env bash
# Stop hook: lightweight structural convention spot-check on changed Python files.
# Advisory only (exit 0). Comment-quality findings are owned by comment-pruner.sh.
set -uo pipefail

CHANGED_FILES=$(git diff --name-only HEAD 2>/dev/null || true)
STAGED_FILES=$(git diff --cached --name-only 2>/dev/null || true)
UNTRACKED=$(git ls-files --others --exclude-standard 2>/dev/null || true)
ALL_FILES=$(printf '%s\n%s\n%s\n' "$CHANGED_FILES" "$STAGED_FILES" "$UNTRACKED" | sort -u | grep -E '\.py$' || true)

if [ -z "$ALL_FILES" ]; then
  exit 0
fi

WARNINGS=""

while IFS= read -r file; do
  [ -f "$file" ] || continue
  case "$file" in */.venv/*|*/__pycache__/*) continue ;; esac

  # Bare `except:` swallows KeyboardInterrupt/SystemExit — catch Exception or narrower.
  if grep -nE '^\s*except\s*:' "$file" >/dev/null 2>&1; then
    WARNINGS+="  ⚠ $file: bare 'except:' — catch a specific exception (see docs/conventions/general.md)\n"
  fi

  # Wildcard imports pollute the namespace and defeat linters.
  if grep -nE '^\s*from\s+\S+\s+import\s+\*' "$file" >/dev/null 2>&1; then
    WARNINGS+="  ⚠ $file: wildcard 'import *' — import names explicitly\n"
  fi

  # datetime.utcnow() is deprecated in 3.12+ and returns a naive datetime.
  if grep -nE 'datetime\.utcnow\s*\(' "$file" >/dev/null 2>&1; then
    WARNINGS+="  ⚠ $file: datetime.utcnow() is deprecated — use datetime.now(timezone.utc)\n"
  fi

  # print() in library code — use the module logger (cli.py uses rich/click intentionally).
  if [[ "$file" == ai_daily/* ]] && [[ "$file" != ai_daily/cli.py ]]; then
    if grep -nE '^\s*print\s*\(' "$file" >/dev/null 2>&1; then
      WARNINGS+="  ⚠ $file: print() in library code — use logging (see docs/conventions/general.md)\n"
    fi
  fi
done <<< "$ALL_FILES"

if [ -n "$WARNINGS" ]; then
  echo "" >&2
  echo "Convention spot-check warnings:" >&2
  echo -e "$WARNINGS" >&2
  echo "These are advisory — fix before committing if possible." >&2
fi

exit 0
