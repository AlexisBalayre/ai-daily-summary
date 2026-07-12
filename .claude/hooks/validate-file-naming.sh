#!/usr/bin/env bash
# PreToolUse(Write) hook — blocks new Python modules with non-PEP8 names.
# Python modules are snake_case: lowercase letters, digits, underscores only.
# Exit 0 = allow, Exit 2 = block with message.
set -euo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# No file path — skip.
if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Only check .py files.
if [[ ! "$FILE_PATH" =~ \.py$ ]]; then
  exit 0
fi

# Only check project source + tests; skip migrations, venv, build artefacts.
# Anchor with (^|/) so both absolute (/Users/.../ai_daily/…) and repo-relative
# (ai_daily/…) paths match.
if [[ ! "$FILE_PATH" =~ (^|/)(ai_daily|tests)/ ]]; then
  exit 0
fi
if [[ "$FILE_PATH" =~ /(\.venv|migrations|versions|__pycache__)/ ]]; then
  exit 0
fi

FILENAME=$(basename "$FILE_PATH")

# Dunder modules are always allowed (__init__.py, __main__.py, conftest.py).
if [[ "$FILENAME" =~ ^__[a-z0-9_]+__\.py$ ]] || [[ "$FILENAME" == "conftest.py" ]]; then
  exit 0
fi

# snake_case module: starts with a lowercase letter or underscore, then
# lowercase letters / digits / underscores. No hyphens, no camelCase, no caps.
if [[ "$FILENAME" =~ ^[a-z_][a-z0-9_]*\.py$ ]]; then
  exit 0
fi

echo "BLOCKED: Python module '$FILENAME' is not snake_case." >&2
echo "" >&2
echo "Modules must be lowercase with underscores: lowercase letters, digits, and '_' only." >&2
echo "  DO:    gmail_extractor.py, summary_generator.py, test_enrichment.py" >&2
echo "  DON'T: GmailExtractor.py (PascalCase), summaryGenerator.py (camelCase), summary-generator.py (hyphens)" >&2
echo "" >&2
echo "Allowed exceptions: __init__.py, __main__.py, conftest.py" >&2
exit 2
