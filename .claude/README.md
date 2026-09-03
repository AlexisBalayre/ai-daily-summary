# Claude Code Configuration

This directory contains all Claude Code customizations for AI Daily Summary. Everything here extends Claude's agentic loop: the cycle of reasoning, tool use, and iteration that powers every session.

## How It All Fits Together

```
┌─────────────────────────────────────────────────────────┐
│                    Always-On Context                     │
│  CLAUDE.md (project rules, build commands)               │
│  Rules without paths (unconditional)                     │
│  Skill descriptions (names + one-liners)                 │
│  MCP tool schemas                                        │
├─────────────────────────────────────────────────────────┤
│                    On-Demand Context                      │
│  Rules with paths (load when matching files opened)      │
│  Skill full content (load when invoked/relevant)         │
│  Subdirectory CLAUDE.md files                            │
├─────────────────────────────────────────────────────────┤
│                    Isolated Context                       │
│  Subagents (own context window, return summary)          │
├─────────────────────────────────────────────────────────┤
│                    External (Zero Cost)                   │
│  Hooks (shell scripts, no LLM, deterministic)            │
└─────────────────────────────────────────────────────────┘
```

**Context budget matters.** Everything in "Always-On" consumes tokens every turn. Rules with `paths:` and skills with descriptions load on-demand, saving context. Subagents run in isolated windows. Hooks cost zero context.

---

## Directory Structure

```
.claude/
├── settings.json               # Shared project config (permissions, hooks, status line)
├── settings.local.json.example # Template for personal overrides (real file gitignored)
├── statusline.sh               # Renders the 3-line status bar (dir · branch · model, context, cost)
│
├── rules/                 # Path-scoped convention rules (auto-load)
│   ├── universal-conventions.md      **/*.py
│   ├── etl-conventions.md            ai_daily/etl/**
│   ├── api-conventions.md            ai_daily/api/**
│   ├── database-conventions.md       ai_daily/db/** (incl. migrations)
│   ├── outputs-conventions.md        ai_daily/outputs/**
│   ├── orchestrator-conventions.md   ai_daily/orchestrator/**
│   ├── testing-conventions.md        tests/**, **/test_*.py
│   └── frontend-conventions.md       frontend/**
│
├── skills/                # Auto-discoverable knowledge + workflows (each is <name>/SKILL.md)
│   ├── tdd/   diagnose/   resolve-merge-conflicts/               # engineering
│   ├── improve-codebase-architecture/                            # engineering (manual)
│   ├── grilling/   grill-me/   codebase-design/                  # thinking / design
│   ├── domain-modeling/   zoom-out/   prototype/
│   ├── pr-description/   pr-ci-review/   address-review-comments/ # PR & review
│   └── write-a-skill/   handoff/   caveman/                      # meta / workflow
│
├── agents/                # Custom subagents for specialized tasks
│   ├── convention-checker.md      migration-reviewer.md          # proactive
│   ├── security-reviewer.md       architecture-explainer.md
│   ├── review-context.md          review-conventions.md          # dispatched by pr-ci-review
│   ├── review-correctness.md      review-docs.md
│   ├── review-maintainability.md  review-security.md
│   ├── review-validator.md
│   └── comment-pruner.md          # dispatched by the comment-pruner Stop hook
│
└── hooks/                    # Deterministic shell scripts (zero LLM cost)
    ├── quality-checks.sh          # Stop: ruff fix + format on dirty .py files
    ├── convention-spot-check.sh   # Stop: advisory scan (bare except, import *, utcnow, print)
    ├── comment-pruner.sh          # Stop: dispatch the comment-pruner subagent on new comments
    ├── git-safety.sh              # PreToolUse(Bash): block dangerous git/shell ops, protect master
    ├── protect-generated.sh       # PreToolUse(Edit|Write): block ai_daily/static/, uv.lock, *.pyc
    ├── validate-file-naming.sh    # PreToolUse(Write): enforce snake_case .py modules
    └── pre-compact-preserve.sh    # PreCompact: inject must-preserve context
```

---

## Extension Points Explained

### 1. `CLAUDE.md` — Project Memory

The root `CLAUDE.md` contains universal rules Claude sees every session: the module map, coding standards, git workflow, key commands. Kept short to minimize context cost.

**When to edit:** Add universal rules that apply to every file. For area-specific rules, use `rules/` instead.

### 2. `rules/` — Path-Scoped Convention Rules

Markdown files with `paths:` frontmatter that auto-load when Claude works with matching files. Each rule is a thin trigger carrying an `@docs/conventions/X.md` import for the full doc.

```yaml
---
paths:
  - "ai_daily/api/**/*.py"
---

@docs/conventions/api.md
```

**Key insight:** Rules follow the "split pattern" — lightweight recognition triggers pointing to detailed knowledge (the full convention docs in `docs/conventions/`, the single source of truth). This keeps always-on context small while ensuring full detail loads when needed.

**When to add a rule:** When conventions are specific to a file path pattern and should auto-load when editing those files.

**Catalog:** [`rules/README.md`](rules/README.md) — every rule, its path scope, and what it enforces.

### 3. `skills/` — Auto-Discoverable Workflows

Skills are directories with a `SKILL.md` that Claude discovers automatically. Claude sees the description at session start (tiny context cost) and loads the full content when the skill is relevant.

This repo ships **16 skills** across engineering, thinking/design, PR & review, and meta/workflow. The **[skill catalog](skills/README.md)** lists when each one fires and how to invoke it (auto-trigger, `/slash-command`, or manual-only).

**Frontmatter options:**
- `name` — identifier and `/slash-command` name
- `description` — when to auto-activate (critical for discovery)
- `user-invocable: false` — Claude-only (hidden from `/` menu)
- `disable-model-invocation: true` — user-only (Claude can't auto-trigger)
- `allowed-tools` — tools available without permission prompts
- `context: fork` — run in isolated subagent context
- `model` — override model when active

**When to add a skill:** When Claude should auto-discover and apply knowledge or follow a workflow without being asked. Skills are for things Claude should know to do on its own. For repeatable workflows only the user should trigger — anything with side effects like posting PR comments — set `disable-model-invocation: true`: a manual-only skill is invoked as `/<name>` and replaces the deprecated `commands/` layer.

### 4. `agents/` — Custom Subagents

Specialized AI workers that run in their own context window. Claude delegates to them and gets summarized results back — zero bloat in the main conversation.

| Agent | Model | Tools | Purpose |
|-------|-------|-------|---------|
| `convention-checker` | Haiku | Read, Glob, Grep | Fast convention compliance audit against `docs/conventions/*.md` |
| `migration-reviewer` | Sonnet | Read, Glob, Grep | Schema + Alembic migration safety review |
| `security-reviewer` | Opus | Read, Glob, Grep, Bash | Deep security analysis (HTML email escaping, SSRF, OAuth tokens, API input) |
| `architecture-explainer` | Sonnet | Read, Glob, Grep | Answer why/how architecture questions, grounded in `README.md`, `docs/conventions/`, `docs/design/`, and the code |
| `review-*` (7 agents) | Sonnet/Opus | Read, Glob, Grep, Bash | Area reviewers + adversarial validator, dispatched by the `pr-ci-review` skill |
| `comment-pruner` | Sonnet | Read, Edit, Grep, Glob, Bash | Prune low-value comments; dispatched by the `comment-pruner.sh` Stop hook |

**Frontmatter options:**
- `tools` — allowlist of tools (restricts to only what's needed)
- `model` — `haiku` (fast/cheap), `sonnet` (balanced), `opus` (deep reasoning)
- `memory: project` — persistent knowledge across sessions
- `isolation: worktree` — run in temporary git worktree
- `skills` — preload specific skills into subagent context
- `mcpServers` — scope MCP servers to this subagent only
- `maxTurns` — limit agentic turns

**When to add an agent:** For tasks that need deep analysis without polluting the main context, or for work that benefits from model-specific strengths (Haiku for speed, Opus for reasoning).

**Catalog:** [`agents/README.md`](agents/README.md) — every agent, when it fires, and its model/tools.

### 5. `hooks/` — Deterministic Automation

Shell scripts that run outside the LLM loop on lifecycle events. Zero context cost, zero hallucination risk — purely deterministic.

| Hook | Event | What it does |
|------|-------|-------------|
| `quality-checks.sh` | Stop | `ruff check --fix` + `ruff format` on the session's dirty `.py` files (blocks on unfixable lint; tests are not run here) |
| `convention-spot-check.sh` | Stop | Advisory scan for bare `except:`, `import *`, `datetime.utcnow()`, `print()` in `ai_daily/` |
| `comment-pruner.sh` | Stop | Dispatch the `comment-pruner` subagent when the session added net-new comments |
| `git-safety.sh` | PreToolUse(Bash) | Block `rm -rf`, `DROP TABLE`, `git reset --hard`, force push, `checkout -b` on `master`, push to `master` |
| `protect-generated.sh` | PreToolUse(Edit\|Write) | Block edits to `ai_daily/static/`, `uv.lock`, and `*.pyc` |
| `validate-file-naming.sh` | PreToolUse(Write) | Enforce `snake_case` on new `.py` files under `ai_daily/` and `tests/` |
| `pre-compact-preserve.sh` | PreCompact | Preserve branch, modified files, test output across compaction |

**Exit codes:**
- `0` — success, continue
- `1` — error (shown to user, continues)
- `2` — **block the operation** (PreToolUse: prevents tool; Stop: feedback to Claude)

**When to add a hook:** For deterministic checks that should always run. If it doesn't need LLM reasoning, it's a hook.

**Catalog:** [`hooks/README.md`](hooks/README.md) — every hook, the event it fires on, and what it does.

### 6. `settings.json` — Permissions & Hook Wiring

Shared project configuration. Contains:
- **`permissions.allow`** — pre-approved tool patterns (`uv run …`, `npm run build|lint`, git read-only and branch ops, `gh pr`)
- **`permissions.deny`** — explicitly blocked operations (force push, hard reset, `rm -rf`) and secret files (`.env`, `.env.local`, `token.json`, credentials)
- **`permissions.ask`** — always confirm (`git checkout`, `git rebase`, `git cherry-pick`)
- **`hooks`** — wires the seven hook scripts to lifecycle events
- **`statusLine`** — runs `statusline.sh`

**`settings.local.json`** (gitignored) extends this with personal preferences — extra permissions, machine-specific tools, and MCP servers such as the local `aidaily` server (`scripts/aidaily_mcp.py`). Copy `settings.local.json.example` to `settings.local.json` to start; it is merged on top of `settings.json`, never replacing it.

---

## Decision Framework

| I want... | Use... |
|-----------|--------|
| Claude to always know this | `CLAUDE.md` |
| Claude to know this when editing specific files | `rules/` with `paths:` |
| Claude to auto-discover and use this knowledge | `skills/` |
| A workflow I trigger explicitly | `skills/` with `disable-model-invocation: true` |
| Isolated analysis that won't bloat context | `agents/` |
| A check that runs every time, deterministically | `hooks/` |
| External service access | MCP server in `settings.local.json` (`mcpServers`) |

---

## Adding New Extensions

### New rule
1. Create `.claude/rules/<name>.md` with `paths:` frontmatter
2. Point to the full doc with `@docs/conventions/<area>.md` (write that doc if it does not exist)
3. Add a row to `rules/README.md`

### New skill
1. Create `.claude/skills/<name>/SKILL.md` with `name` and `description` frontmatter (see `/write-a-skill`)
2. Write the full workflow/knowledge content
3. Set `user-invocable: false` if Claude-only, `disable-model-invocation: true` if user-only
4. Add a row to `skills/README.md`

### New agent
1. Create `.claude/agents/<name>.md` with `name`, `description`, and `tools`
2. Choose `model` based on task complexity (haiku/sonnet/opus)
3. Restrict `tools` to minimum needed
4. Add a row to `agents/README.md`

### New hook
1. Create `.claude/hooks/<name>.sh` (must be executable)
2. Wire it in `settings.json` under the appropriate event
3. Use exit code `2` to block operations
4. Add a row to `hooks/README.md`
