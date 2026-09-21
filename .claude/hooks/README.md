# Hook catalog

Hooks are deterministic shell scripts wired in [`settings.json`](../settings.json) that run on
lifecycle events — zero LLM cost, zero context, no hallucination. You never invoke them; they
fire automatically. Exit code `2` blocks the operation, `0` allows it.

Stack-specific values (commands, generated paths, naming pattern, trunk) come from
[`.claude/project.env`](../project.env), filled by `/adapt-to-project`. An empty value turns the
check off, so every hook no-ops harmlessly until the project is adapted.

| Hook | Fires on | What it does |
| :--- | :------- | :----------- |
| `quality-checks.sh` | `Stop` | When source files (`SOURCE_EXTENSIONS`: `.py`) are dirty: `FORMAT_FIX_CMD` (`ruff check --fix` + `ruff format`) then `LINT_CMD` (`ruff check`) on the dirty files only, so unrelated red on `master` can't block a session. No `TYPECHECK_CMD` is set. Blocks (exit 2) if ruff can't auto-fix something. Tests are deliberately not run here: `scripts/pre-commit` runs `TEST_CMD`. |
| `convention-spot-check.sh` | `Stop` | Runs the checks in [`.claude/spot-checks.tsv`](../spot-checks.tsv) (path regex, forbidden content regex, message) over the session's changed and untracked files: `print()` in library code, sync `requests` in `ai_daily/api/`. Blocks once (exit 2) so findings actually reach the model (exit-0 output never does), then stays silent on the `stop_hook_active` re-run so a heuristic misfire cannot loop. Ruff already covers `utcnow()`, bare `except:` and `import *`. |
| `comment-pruner.sh` | `Stop` | When the session added net-new comments (hashed against a memo of already-adjudicated ones): exits 2 so the main loop dispatches the `comment-pruner` subagent over the touched files, then seals the memo. Skips `migrations/` (Alembic scaffolding) and generated paths. A cheap pre-filter: a response that adds no comment pays nothing. |
| `git-safety.sh` | `PreToolUse(Bash)` | Blocks `rm -rf`, `DROP TABLE`, `git push --force`, `git reset --hard`, `checkout -b` on the trunk, and pushes to the trunk. Trunk name from `GIT_TRUNK` (`master` here). |
| `protect-generated.sh` | `PreToolUse(Edit\|Write)` | Blocks edits to paths matching `GENERATED_PATHS_REGEX`: the built dashboard `ai_daily/static/` (`cd frontend && npm run build`), `uv.lock` (`uv lock`), `package-lock.json` (`npm install`), and `*.pyc` / `__pycache__/`. |
| `validate-file-naming.sh` | `PreToolUse(Write)` | Blocks new `.py` files under `ai_daily/` or `tests/` whose name isn't snake_case (`FILE_NAMING_REGEX`), showing `FILE_NAMING_HINT`. Overwrites of existing files and paths outside `$CLAUDE_PROJECT_DIR` pass. |
| `pre-compact-preserve.sh` | `PreCompact` | Injects must-preserve context (current branch + worktree path, modified files, test results) so it survives compaction. |

**Configure / disable:** edit the entry under `hooks` in `settings.json`. Scripts must stay
executable (`chmod +x`) and need `jq` on `PATH` (`git-safety.sh`, `validate-file-naming.sh`,
`statusline.sh`). To add a hook, see [`.claude/README.md`](../README.md) ("New hook").
