---
name: resolving-merge-conflicts
description: Resolve an in-progress git merge or rebase conflict. Use when a merge, rebase, or cherry-pick stops on conflicts.
---

1. **See the current state** of the merge/rebase. Check `git status`, the git history of both sides, and the conflicting files.

2. **Find the primary sources** for each conflict. Understand deeply why each change was made, and what the original intent was. Read the commit messages and the PRs (`gh pr view`); the PR body, any issue it references, and the design docs under `docs/design/` and `docs/adr/` are the record of intent.

3. **Resolve each hunk.** Preserve both intents where possible. Where incompatible, pick the one matching the merge's stated goal and note the trade-off. Do **not** invent new behaviour. Always resolve; never `--abort`.

4. **Regenerate, don't hand-merge.** Conflict markers in generated files are never resolved by hand:
   - `uv.lock`: take either side wholesale, then re-run `uv lock` (and `uv sync`) against the merged `pyproject.toml` to regenerate. The `protect-generated` hook blocks editing it anyway.
   - `frontend/package-lock.json`: take either side wholesale, then re-run `cd frontend && npm install` against the merged `package.json`.
   - Alembic migrations under `ai_daily/db/migrations/versions/`: two branches that each added a migration produce two heads, not a textual conflict. Keep both files, re-point the newer one's `down_revision` at the other branch's revision id so the chain is linear, then verify with `uv run alembic heads` (exactly one head) and `uv run alembic upgrade head` on a scratch database. Never merge two migrations into one file, and never edit a migration that has already been applied elsewhere.
   - `ai_daily/static/`: never merge. It is the built dashboard (git-ignored in normal use); delete whatever the merge left there and rebuild with `cd frontend && npm run build`.
   - Any other generated artifact: re-run its generator against the merged sources; never edit the output.

5. **Run the automated checks** and fix anything the merge broke. Ruff lint + format run automatically via the Stop hook; run the tests yourself (`uv run pytest`, scoped to the affected area when you can), and `cd frontend && npm run lint` if frontend files were involved. The pre-commit hook (`scripts/pre-commit`) runs the project's checks and tests; failures that already exist on `master` are not the merge's fault: note them rather than fixing them in the merge commit, and `--no-verify` is acceptable only for those.

6. **Finish the merge/rebase.** Stage everything and commit. If rebasing, continue the rebase process (`git rebase --continue`) until all commits are rebased.
