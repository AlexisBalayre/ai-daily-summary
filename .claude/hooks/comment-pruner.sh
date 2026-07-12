#!/usr/bin/env bash
# Stop hook + memo manager for the autonomous comment-pruner.
#
# check mode (default, the Stop hook): hash the comment lines added since HEAD,
# subtract the memo of already-adjudicated comments, and exit 2 to make the main
# loop dispatch the comment-pruner subagent when anything new remains. A cheap
# pre-filter so a response that adds no comment pays nothing.
#
# seal mode: record every currently-added comment as adjudicated so the next
# Stop does not re-review what the agent just cleared. The main loop runs this
# after the agent returns.
#
# Termination: the memo is the primary brake; stop_hook_active is the hard cap
# (one dispatch per Stop cycle) so a memo hole cannot loop.
set -uo pipefail

cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}" 2>/dev/null || exit 0
command -v git >/dev/null 2>&1 || exit 0

GIT_DIR=$(git rev-parse --git-dir 2>/dev/null) || exit 0
MEMO="$GIT_DIR/comment-pruner-memo"
HEAD_SHA=$(git rev-parse HEAD 2>/dev/null || echo none)
MODE="${1:-check}"

# Generated files and vendored/build dirs carry comments the agent must never
# touch; the agent re-applies this filter, but excluding here avoids dispatching
# for them at all.
EXCLUDE='(/(\.venv|__pycache__|migrations|versions|node_modules)/|\.pyc$)'

TRACKED=$(git diff HEAD --name-only -- '*.py' 2>/dev/null | grep -vE "$EXCLUDE" || true)
UNTRACKED=$(git ls-files --others --exclude-standard -- '*.py' 2>/dev/null | grep -vE "$EXCLUDE" || true)

# Source lines added versus HEAD: diff-added lines for tracked files, whole
# content for untracked files (a new file's comments are all newly written).
added_source() {
  if [ -n "$TRACKED" ]; then
    printf '%s\n' "$TRACKED" | xargs git diff HEAD --unified=0 -- 2>/dev/null \
      | grep -E '^\+[^+]' | sed -E 's/^\+//'
  fi
  if [ -n "$UNTRACKED" ]; then
    printf '%s\n' "$UNTRACKED" | while IFS= read -r f; do [ -f "$f" ] && cat "$f"; done
  fi
}

# Hash the comment text on each line so a new comment dispatches the pruner.
# Covers Python `#` comments — full-line and trailing. A shebang (`#!` on line 1)
# is skipped. URLs are stripped first so a `#fragment` in an `https://…` literal
# is not read as a comment. The naive scan also matches a `#` inside a string
# literal; accepted on purpose, because the only cost is one spurious dispatch
# bounded by the memo and stop_hook_active. Hashing the comment text, not the
# whole line, means editing surrounding code does not re-trigger.
extract_hashes() {
  awk '
    NR==1 && $0 ~ /^#!/ { next }
    {
      c=""
      tmp=$0; gsub(/[a-zA-Z][a-zA-Z0-9+.-]*:\/\/[^[:space:]]*/,"",tmp)
      h=index(tmp,"#")
      if (h>0) c=substr(tmp,h)
      gsub(/^[[:space:]]+/,"",c); gsub(/[[:space:]]+$/,"",c)
      if (c!="") print c
    }
  ' \
    | while IFS= read -r l; do printf '%s' "$l" | shasum -a 256 | cut -d' ' -f1; done \
    | sort -u
}

if [ "$MODE" = "seal" ]; then
  { printf '%s\n' "$HEAD_SHA"; added_source | extract_hashes; } > "$MEMO"
  exit 0
fi

# check mode
STOP_HOOK_ACTIVE=false
if [ ! -t 0 ]; then
  INPUT=$(cat 2>/dev/null || true)
  printf '%s' "$INPUT" | grep -q '"stop_hook_active"[[:space:]]*:[[:space:]]*true' && STOP_HOOK_ACTIVE=true
fi

CUR=$(added_source | extract_hashes)
[ -z "$CUR" ] && exit 0

# Memo is valid only while HEAD is unchanged; a commit moves the diff base and
# resets it.
MEMO_H=""
if [ -f "$MEMO" ] && [ "$(head -n1 "$MEMO" 2>/dev/null)" = "$HEAD_SHA" ]; then
  MEMO_H=$(tail -n +2 "$MEMO" 2>/dev/null | sort -u)
fi

NETNEW=$(comm -23 <(printf '%s\n' "$CUR") <(printf '%s\n' "$MEMO_H"))
[ -z "$NETNEW" ] && exit 0

COUNT=$(printf '%s\n' "$NETNEW" | grep -c .)
if [ "$STOP_HOOK_ACTIVE" = true ]; then
  printf '\ncomment-pruner: %s net-new comment line(s) still flagged after one dispatch this cycle; advisory only.\n' "$COUNT" >&2
  exit 0
fi

FILES=$(printf '%s\n%s\n' "$TRACKED" "$UNTRACKED" | grep -vE '^$' | sort -u)
{
  printf '\ncomment-pruner: %s net-new comment line(s) added this session.\n' "$COUNT"
  printf 'Dispatch the comment-pruner subagent (Agent tool, subagent_type: comment-pruner) to prune the\n'
  printf 'comments ADDED versus HEAD in the files below, then run from the repo root:\n'
  printf '  .claude/hooks/comment-pruner.sh seal\n\n'
  printf 'Files:\n%s\n' "$FILES"
} >&2
exit 2
