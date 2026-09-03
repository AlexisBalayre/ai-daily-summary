---
name: resolve-merge-conflicts
description: Resolve an in-progress git merge or rebase conflict. Use when a merge, rebase, or cherry-pick stops on conflicts.
---

# Resolve Merge Conflicts

1. **See the current state** of the merge/rebase: `git status`, the history of both sides, and the conflicting files.

2. **Find the primary sources** for each conflict. Understand deeply why each change was made and what the original intent was. Read the commit messages and the PRs (`gh pr view`); there is no issue tracker, so the PR body and any design doc under `docs/design/` are the record of intent.

3. **Resolve each hunk.** Preserve both intents where possible. Where incompatible, pick the one matching the merge's stated goal and note the trade-off. Do **not** invent new behaviour. Always resolve; never `--abort`.

4. **Regenerate, don't hand-merge.** Conflict markers in generated files are never resolved by hand:
   - `uv.lock`: take either side wholesale, then re-run `uv lock` (and `uv sync`) against the merged `pyproject.toml` to regenerate. The `protect-generated` hook blocks editing it anyway.
   - `frontend/package-lock.json`: take either side wholesale, then re-run `cd frontend && npm install` against the merged `package.json`.
   - Alembic migrations under `ai_daily/db/migrations/versions/`: two branches that each added a migration produce two heads, not a textual conflict. Keep both files, re-point the newer one's `down_revision` at the other branch's revision id so the chain is linear, then verify with `uv run alembic heads` (exactly one head) and `uv run alembic upgrade head` on a scratch database. Never merge two migrations into one file, and never edit a migration that has already been applied elsewhere.
   - `ai_daily/static/`: never merge. It is the built dashboard (git-ignored in normal use); delete whatever the merge left there and rebuild with `cd frontend && npm run build`.
   - Any other generated artifact: re-run its generator against the merged sources; never edit the output.

5. **Run the tests**: `uv run pytest`, and `cd frontend && npm run lint` if frontend files were involved. Fix anything the merge broke (ruff lint + format run automatically via the Stop hook). Failures that already exist on `master` are not the merge's fault; note them rather than fixing them in the merge commit.

6. **Finish the merge/rebase.** Stage everything and commit. If rebasing, continue (`git rebase --continue`) until all commits are rebased.
