---
name: pr-description
description: Write a PR title and description in this repo's house style, then create or update the PR via gh. Use when asked to draft or rewrite a PR title or body, to open a PR, or when another skill opens a PR. Assumes commits exist on the branch.
---

# Write a PR title and description

This repo has no issue tracker; the PR body is the record of what changed and why.

## Workflow

1. **Gather context** (run together):

   ```sh
   git branch --show-current                                # MUST NOT be "master"; abort if it is
   git log master..HEAD --pretty=format:'%h %s%n%b'         # commits on this branch
   git diff master...HEAD --stat                            # changed files + churn
   gh pr view --json number,url,state,title,body 2>/dev/null   # non-zero exit = no PR yet
   ```

   Read the diff for the key files (`git diff master...HEAD -- <path>`); on large diffs lean on `--stat` plus the important files.

2. **Select sections** from the diff (table below). Only include sections that apply.

3. **Draft title + body together.** Title per [Title format](#title-format); body to a temp file (`mktemp`) per [TEMPLATE.md](TEMPLATE.md). For an existing PR, treat the current title as a draft, not a constraint.

4. **Create or update the PR.** Show the drafted **title** and **body** + the exact `gh` command; quick confirm before running (notifies reviewers) unless told to just do it.

   ```sh
   git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || git push -u origin "$(git branch --show-current)"
   # update existing; pass --title only if it changes:
   gh pr edit <number> --body-file <tmp> [--title "<drafted title>"]
   # or create new:
   gh pr create --base master --title "<drafted title>" --body-file <tmp>
   ```

   Report the PR URL.

## Title format

Communicate *what changed and why* at a glance, specific enough that a reviewer can predict the diff. GitHub auto-appends ` (#NNNN)` on merge; do not write it yourself.

```
<type>(<scope>): <summary>
```

- **`<type>`**: dominant intent of the diff.

  | Type       | Use for                                     |
  | :--------- | :------------------------------------------ |
  | `feat`     | New feature or capability                   |
  | `fix`      | Bug fix                                     |
  | `refactor` | Code restructuring with no behaviour change |
  | `docs`     | Documentation only                          |
  | `test`     | Adding or updating tests                    |
  | `chore`    | Build config, dependencies, tooling         |
  | `perf`     | Performance improvement                     |

  Mixed diff: pick the user-visible win, mention the rest in `## Notes`.
- **`<scope>`**: optional but usually present. Lowercase kebab. Common scopes in this repo: `etl`, `enrichment`, `api`, `db`, `outputs`, `newsletter`, `tts`, `orchestrator`, `cli`, `frontend`, `mcp`, `tooling`, `deps`, `skills`. Multi-scope `(api,frontend)` only when both are non-trivial. Drop the scope when the change is repo-wide.
- **`<summary>`**: imperative present tense, lowercase first word, no trailing period. Proper nouns keep their case (`Alembic`, `pgvector`, `FastAPI`, `Gemini`); double quotes around identifiers are fine.
- Follow-ups to a prior PR: append `(follow-up to #NNNN)`.

**Lint:**

- No em-dash (`—` / `–`). Hyphen, colon, or rephrase.
- No trailing period; no capital after the colon (proper nouns excepted).
- ≲ 80 chars; if over, trim adjectives, not specificity.
- Reject generic verbs (`update`, `improve`, `change`, `various`). Strong fix-title names cause, surface, impact: `fix(orchestrator): double newsletter send when a retry overlaps a slow run`, not `fix bug`.

**Worked examples** (paired bodies in [TEMPLATE.md](TEMPLATE.md)):

| Diff shape                          | Title |
| :---------------------------------- | :---- |
| Backend + frontend slice            | `feat(api,frontend): source toggle endpoint and enabled switch on the sources page` |
| Targeted backend bug                | `fix(etl): rss extractor drops entries whose published_parsed is None` |
| Schema change with migration        | `feat(db): store model-release flag on articles for the release radar` |
| Docs-only                           | `docs: describe inline enrichment in the ETL conventions` |
| Follow-up to a prior PR             | `docs: scrub em-dashes from the outputs conventions (follow-up to #12)` |
| Repo-wide change, no scope          | `chore: replace datetime.utcnow with timezone-aware now across the package` |

## Section selection

| Section        | Include when                                                                 |
| :------------- | :--------------------------------------------------------------------------- |
| `## Summary`   | Always. One sentence of intent, then concrete bullets of what changed.       |
| `## Changes`   | Any code change with a non-obvious approach or notable design decision.      |
| `## Migration` | `ai_daily/db/models.py` or `ai_daily/db/migrations/versions/**` changed. Name the revision file, state additive/nullable + backwards-compat verdict, and whether `downgrade()` is implemented. |
| `## Behaviour` | New rules, gates, schedules, or edge cases worth flagging (dedup thresholds, retry policy, fallback paths). |
| `## Testing`   | Always for code changes: what `uv run pytest` covers, what was checked by hand (a real ETL run, a rendered email, the dashboard). |
| `## Notes`     | Asides: "docs-only", "no code change", follow-ups deferred.                  |

Omit a `## Reviews` section.

## Body rules

- **No em-dash** (`—` / `–`). Hyphen or colon.
- **No hardcoded hostnames, recipient addresses, or API keys.** Derive from config; never paste `.env` or `config.json` values.
- **No attribution footer.** Never add `🤖 Generated with Claude Code` (or any agent attribution) to the PR body. The `Co-Authored-By` trailer on commits is the only attribution.
