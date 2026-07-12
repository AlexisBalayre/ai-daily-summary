#!/bin/bash
# Protect generated / lockfile artefacts from manual edits.
# Runs as PreToolUse hook on Edit/Write tool calls.

set -o pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | grep -o '"file_path":"[^"]*"' | head -1 | sed 's/"file_path":"//;s/"$//')

# If we can't extract the file path, allow it.
if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Block: built frontend assets served by FastAPI (produced by `npm run build`).
if echo "$FILE_PATH" | grep -qE 'ai_daily/(api/)?static/'; then
  echo "BLOCKED: files under ai_daily/static/ are built from frontend/. Edit the React source and run 'cd frontend && npm run build'." >&2
  exit 2
fi

# Block: uv lockfile — regenerate via uv, never hand-edit.
if echo "$FILE_PATH" | grep -qE '(^|/)uv\.lock$'; then
  echo "BLOCKED: uv.lock is generated. Change dependencies in pyproject.toml and run 'uv lock' / 'uv sync'." >&2
  exit 2
fi

# Block: compiled Python.
if echo "$FILE_PATH" | grep -qE '\.pyc$|/__pycache__/'; then
  echo "BLOCKED: compiled Python artefacts are generated. Do not edit." >&2
  exit 2
fi

exit 0
