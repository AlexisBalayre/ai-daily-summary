---
name: domain-modeling
description: Maintain this repo's documented language as design decisions land. Use when pinning down domain terminology, recording an architectural decision, or when another skill needs the docs kept current during a session.
---

# Domain Modeling

Actively sharpen the project's documented language as you design: challenge terms, stress-test them with edge-case scenarios, and update the docs the moment a decision crystallises. Merely *reading* the docs for vocabulary is not this skill; reach for it when the language is being *changed*, not just consumed.

## Where the documented language lives in this repo

| Source                            | What it covers                                                                          |
| :-------------------------------- | :-------------------------------------------------------------------------------------- |
| `docs/conventions/general.md`     | Naming rules and the glossary of cross-cutting nouns: Source, Article, RawContent, DailySummary, JobRun, extractor, enrichment, newsletter, briefing |
| `docs/conventions/<area>.md`      | Area vocabulary and obligations: `etl.md`, `api.md`, `database.md`, `outputs.md`, `orchestrator.md`, `frontend.md`, `testing.md` |
| `docs/design/<date>-<topic>.md`    | Dated design docs (data platform, orchestrator, enrichment, dashboard, RSS); the closest thing to a rationale log today         |
| `docs/adr/`                       | Dated log of why a hard-to-reverse choice was made. Does not exist yet; created on the first ADR |
| `README.md`                       | User-facing architecture overview and CLI reference                                     |

Before a session, skim `docs/conventions/general.md`, the relevant area doc, and any design doc in `docs/design/` already covering the area. For *why*/*how* questions that span the pipeline, delegate to the `architecture-explainer` subagent rather than re-reading docs in the main context.

## During the session

### Challenge against the existing language

When the user uses a term that conflicts with the conventions, call it out. Example: "`etl.md` defines an extractor as returning `RawContent` and never touching the DB; you're describing something that also upserts Articles. Is that an extractor or part of the pipeline?"

### Sharpen fuzzy language

Propose precise canonical terms; pull from the existing conventions first, only invent when nothing fits. Common ambiguities here:

- "Article" (a stored, enriched `Article` row vs. the `RawContent` an extractor just returned)
- "Summary" (the per-article LLM `summary` column vs. the per-day `DailySummary`)
- "Newsletter" (the HTML email vs. the `newsletter` orchestrator job vs. the Gmail newsletter *sources* it is built from)
- "Briefing" vs. "TTS" vs. "audio" (one deliverable, `tts_briefing.py`)
- "Source" vs. "feed" (a feed is only the RSS kind of Source)
- "Duplicate" (content-hash dedup in the transformer vs. semantic dedup at enrichment time)

### Stress-test with concrete scenarios

Force precision with edge cases that touch package boundaries:

- "The same story arrives from an RSS feed and a Gmail newsletter an hour apart. Which Article survives, and which `is_duplicate`?"
- "Enrichment fails for half a batch because Gemini rate-limits. Are those Articles stored unenriched, retried, or dropped? What does the newsletter show for them?"
- "The `newsletter` job retries after a partial send. Which recipients get it twice?"
- "A source is disabled after its Articles were ingested. Do they still appear in the daily summary?"

### Cross-reference with code

When the user states how something works, verify against the code in the relevant package (`ai_daily/etl/`, `ai_daily/outputs/`, `ai_daily/orchestrator/`, `ai_daily/api/`, `frontend/src/`). Surface contradictions: "`summary_generator.py` regenerates the `DailySummary` only when newer articles exist, but you said every run rewrites it. Which is right?"

### Update the existing docs inline

When something resolves, update it in place. Capture as it happens; don't batch.

- **New cross-cutting noun?** Add it to the glossary in `docs/conventions/general.md` (create the section on first use; entry format in [CONTEXT-FORMAT.md](./CONTEXT-FORMAT.md)).
- **Naming or area-obligation decision?** Update the relevant `docs/conventions/<area>.md`.
- **Architecture overview has drifted from reality?** Update `README.md`.
- **Hard-to-reverse choice with non-obvious rejected alternatives?** Open an ADR.

Do not create a parallel `CONTEXT.md`. See [CONTEXT-FORMAT.md](./CONTEXT-FORMAT.md) for the underlying glossary discipline if you need a reminder of what a good entry looks like.

### Offer ADRs sparingly

Only offer an ADR when all three are true:

1. **Hard to reverse**: the cost of changing your mind later is meaningful
2. **Surprising without context**: a future reader will wonder "why did they do it this way?"
3. **The result of a real trade-off**: there were genuine alternatives and one was picked for specific reasons

If any of the three is missing, skip it. See [ADR-FORMAT.md](./ADR-FORMAT.md) for the bar and template; `docs/adr/` is created on the first ADR.
