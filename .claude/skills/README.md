# Skill catalog

Each skill is a `<name>/SKILL.md`. Claude sees only the one-line description at session start
and loads the full skill when it is relevant. This catalog says **when** each fires and **how**
to invoke it.

**Invoke legend**
- **Auto or `/name`** — Claude triggers on the cue described; you can also run `/name` yourself.
- **Manual only** — you invoke it; Claude never auto-triggers (`disable-model-invocation: true`).

## Setup — fit the config to the project

| Skill | When to use | Invoke |
| :---- | :---------- | :----- |
| `adapt-to-project` | When the project grows a new area (a new package under `ai_daily/`, a new top-level service) or `.claude/project.env` drifts from the real commands. Fills whatever is still `TODO(adapt)` or the area you name; never overwrites filled content without asking. | Manual only (`/adapt-to-project`) |

## Planning & specs — from idea to tickets

`to-spec`, `to-tickets` and `wayfinder` publish to an issue tracker only when an issue-tracker MCP server and its `TRACKER_*` IDs are configured. This repo has none, so they write local Markdown under `docs/plans/<slug>/` (local-only: `scripts/pre-commit` refuses to commit it).

| Skill | When to use | Invoke |
| :---- | :---------- | :----- |
| `to-spec` | Turn the current conversation into a spec: no interview, just synthesis of what was already discussed. | Manual only (`/to-spec`) |
| `to-tickets` | Break a plan, spec, or conversation into tracer-bullet tickets, each declaring its blocking edges. | Manual only (`/to-tickets`) |
| `wayfinder` | Plan work too big for one agent session as a shared map of decision tickets, then resolve them one at a time. | Manual only (`/wayfinder`) |
| `implement` | Implement a spec or set of tickets: TDD, `uv run pytest`, a self-review against the acceptance criteria, then commit on a feature branch. | Manual only (`/implement`) |
| `to-questionnaire` | A decision you can't answer alone: turn it into a questionnaire for the one person who can. | Manual only (`/to-questionnaire`) |

## Engineering — build, fix, and clean up

| Skill | When to use | Invoke |
| :---- | :---------- | :----- |
| `tdd` | Building a feature or fixing a bug test-first; "red-green-refactor"; want integration tests. Drives the red → green loop with pytest + `unittest.mock` (refactoring belongs to the review stage, not the loop). | Auto or `/tdd` |
| `diagnosing-bugs` | A hard bug or performance regression; "diagnose/debug this"; something broken, throwing, failing, or slow. Builds a feedback loop first and redacts secrets (Gmail tokens, API keys) from anything it shows. | Auto or `/diagnosing-bugs` |
| `resolving-merge-conflicts` | A merge, rebase, or cherry-pick stopped on conflicts. Resolves by intent, and regenerates — never hand-merges — `uv.lock`, `package-lock.json`, Alembic heads, and `ai_daily/static/`. | Auto or `/resolving-merge-conflicts` |
| `wizard` | A step only a human can do (Google Cloud OAuth consent screen, Gmail credentials, CI secrets): generates an interactive bash wizard that walks them through it. | Auto or `/wizard` |
| `research` | Research a question against primary sources and save the cited findings to `docs/research/<slug>.md`. | Auto or `/research` |
| `find-dead-code` | "find dead code" / "unused exports" / "prune the codebase". Returns a ranked candidate list with a per-item verification checklist; it never deletes. | Manual only (`/find-dead-code`) |
| `improve-codebase-architecture` | "improve architecture" / "find refactors" / "make it more testable". Scans for deepening opportunities, presents a visual HTML report, then grills through whichever one you pick. | Manual only (`/improve-codebase-architecture`) |

## Thinking & design — get to clarity before coding

| Skill | When to use | Invoke |
| :---- | :---------- | :----- |
| `prototype` | Sanity-check a data model / state machine, or mock up UI, before committing. Logic prototypes are one shareable HTML file (or `uv run python prototypes/<name>.py` when they must run the Python code); UI variations run on a throwaway Vite route. The prototype is kept on a throwaway branch as evidence. | Auto or `/prototype` |
| `grilling` | The shared grilling core: rounds of numbered questions, each with a recommended answer, until no open question remains. Facts come from the codebase, decisions from you. | Auto or `/grilling` |
| `grill-me` | Thin wrapper: a plain grilling session on your plan or design. | Manual only (`/grill-me`) |
| `grill-with-docs` | Thin wrapper: grilling plus `domain-modeling`, so the glossary and ADRs are updated as decisions land. | Manual only (`/grill-with-docs`) |
| `codebase-design` | Shared vocabulary for deep modules: interfaces, seams, testability, design-it-twice. Other skills call it. | Auto or `/codebase-design` |
| `domain-modeling` | Build and sharpen the domain model in `docs/glossary.md` and `docs/adr/` while discussing terminology or decisions (Source vs. feed, Article vs. RawContent, summary vs. DailySummary). | Auto or `/domain-modeling` |
| `zoom-out` | You're unfamiliar with an area and want a higher-level map of the relevant modules and callers. | Manual only (`/zoom-out`) |

## PR & review — from branch to merged

| Skill | When to use | Invoke |
| :---- | :---------- | :----- |
| `pr-description` | Draft or rewrite a PR title/body in the repo's house style (Summary / Changes / Migration / Behaviour / Testing / Notes), then create or update the PR via `gh`. Other skills call it when they open PRs. | Auto or `/pr-description` |
| `pr-ci-review` | Cost-optimal multi-agent code review of local changes or a PR: ruff + pytest pre-flight (local), relevance-gated `review-*` subagents, a validation pass, and a structured record. In CI, `.github/workflows/claude-code-review.yml` runs it and posts the record to the PR. | Manual only (`/pr-ci-review`) |
| `address-review-comments` | Triage, decide, challenge, and implement a PR's open review threads end to end, replying as you go, with a human in the loop. | Auto or `/address-review-comments` |
| `review-retro` | Mine past automated-review runs for recurring process/judgment failures and propose evidence-cited fixes to the review setup as one PR. Needs the CI review's run history on the `ci/review-metrics` branch. | Manual only (`/review-retro`) |

## Meta & workflow

| Skill | When to use | Invoke |
| :---- | :---------- | :----- |
| `writing-for-agents` | Create or edit a skill, `AGENTS.md`, or `CLAUDE.md` well: context pointers, information hierarchy, leading words, invocation mechanics, and this repo's house rules. | Manual only (`/writing-for-agents`) |
| `handoff` | Compact the current conversation into a handoff document for another agent or a fresh session. | Manual only (`/handoff`) |
| `wait-what` | A message didn't land: the agent re-pitches it with context, plain language, and the glossary's terms. | Manual only (`/wait-what`) |
| `caveman` | Ultra-compressed replies (~75% fewer tokens) with full technical accuracy; "caveman mode", "be brief". | Auto or `/caveman` |

The planning, engineering, thinking and meta skills track [mattpocock/skills](https://github.com/mattpocock/skills), adapted to this repo's docs layout and `.claude/project.env`.
