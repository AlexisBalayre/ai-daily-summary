# Hook catalog

Hooks are deterministic shell scripts wired in [`settings.json`](../settings.json) that run on
lifecycle events — zero LLM cost, zero context, no hallucination. You never invoke them; they
fire automatically. Exit code `2` blocks the operation, `0` allows it.

| Hook | Fires on | What it does |
| :--- | :------- | :----------- |
| `quality-checks.sh` | `Stop` | When `.py` files are dirty (modified, staged, or untracked): `uv run ruff check --fix` then `uv run ruff format` on those files only, then a final `ruff check`. Blocks (exit 2) if something remains that ruff cannot auto-fix. No-ops when no Python changed, and skips with a notice if `uv` is not on `PATH`. Tests are deliberately not run here; run `uv run pytest` yourself. Whole-repo lint is avoided on purpose so unrelated red on `master` cannot block a session. |
| `convention-spot-check.sh` | `Stop` | Advisory scan of changed `.py` files for a bare `except:`, wildcard `import *`, `datetime.utcnow()`, and `print()` in library code under `ai_daily/` (the CLI is exempt). Always advisory (exit 0). Comment quality is owned by `comment-pruner.sh`. |
| `comment-pruner.sh` | `Stop` | When the session added net-new `#` comments versus `HEAD` (hashed against a memo of already-adjudicated ones in `.git/comment-pruner-memo`): exits 2 so the main loop dispatches the `comment-pruner` subagent over the touched files, then `comment-pruner.sh seal` records them. Skips `.venv/`, `__pycache__/`, migrations, and `node_modules/`. One dispatch per Stop cycle at most. |
| `git-safety.sh` | `PreToolUse(Bash)` | Blocks `rm -rf`, `DROP TABLE`, `git push --force`, `git reset --hard`, `git checkout -b` while on the trunk, any push whose refspec targets the trunk, and a bare `git push` while on the trunk. Trunk is `master` (override with `GIT_TRUNK`). |
| `protect-generated.sh` | `PreToolUse(Edit\|Write)` | Blocks edits to the built dashboard under `ai_daily/static/`, to `uv.lock`, and to `*.pyc` / `__pycache__/`. Rebuild with `cd frontend && npm run build`, regenerate the lockfile with `uv lock`. |
| `validate-file-naming.sh` | `PreToolUse(Write)` | Blocks new `.py` files under `ai_daily/` or `tests/` whose name is not `snake_case` (`gmail_extractor.py`, not `GmailExtractor.py`). Dunder modules and `conftest.py` are allowed; migrations, `.venv`, and `__pycache__` are skipped. |
| `pre-compact-preserve.sh` | `PreCompact` | Injects must-preserve context (current branch + worktree path, modified files, test commands and results, error output) so it survives compaction. |

**Configure / disable:** edit the entry under `hooks` in `settings.json`. Scripts must stay
executable (`chmod +x`) and need `jq` on `PATH` (`git-safety.sh`, `validate-file-naming.sh`,
`statusline.sh`). To add a hook, see [`.claude/README.md`](../README.md) ("New hook").
