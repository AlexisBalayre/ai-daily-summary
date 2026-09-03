# Glossary entry format

This repo keeps its glossary in `docs/conventions/general.md` (a Naming/Glossary section), not in a parallel `CONTEXT.md`. The discipline below is what a good entry looks like; apply it there.

## Structure

```md
# {Context Name}

{One or two sentence description of what this context is and why it exists.}

## Language

**Source**:
A configured place articles come from (a Gmail newsletter sender, an RSS feed, GitHub trending, a crawled site). Rows in `sources`; each has a `type` that selects its extractor.
_Avoid_: feed (that is only the RSS kind), provider, channel

**Article**:
One normalized, deduplicated item stored in `articles`, carrying its enrichment (`summary`, `category`, `is_ai_related`, embedding).
_Avoid_: item, entry, post

**RawContent**:
What an extractor returns before transformation: unstored, unenriched, may still be a duplicate.
_Avoid_: article (an Article exists only after storage)

**DailySummary**:
The cached per-day digest generated from enriched Articles; regenerated only when newer articles exist.
_Avoid_: newsletter (the newsletter is the email built from it), briefing

**JobRun**:
One recorded execution of an orchestrator job (`etl`, `newsletter`, `tts`) with start, status, and error.
_Avoid_: task, run (bare)
```

## Rules

- **Be opinionated.** When multiple words exist for the same concept, pick the best one and list the others as aliases to avoid.
- **Flag conflicts explicitly.** If a term is used ambiguously, call it out in "Flagged ambiguities" with a clear resolution.
- **Keep definitions tight.** One or two sentences max. Define what it IS, not what it does.
- **Show relationships.** Use bold term names and express cardinality where obvious.
- **Only include terms specific to this project's context.** General programming concepts (timeouts, error types, utility patterns) don't belong even if the project uses them extensively. `Extractor`, `enrichment`, `newsletter`, and `briefing` belong; `retry` and `session` do not. Before adding a term, ask: is this a concept unique to this context, or a general programming concept? Only the former belongs.
- **Group terms under subheadings** when natural clusters emerge. If all terms belong to a single cohesive area, a flat list is fine.
- **Write an example dialogue.** A conversation between a dev and a domain expert that demonstrates how the terms interact naturally and clarifies boundaries between related concepts.

## Where entries go in this repo

This is a single-context repo: one glossary, in `docs/conventions/general.md`. Add the Glossary section there the first time a cross-cutting term is pinned down (it does not exist yet). Area-specific vocabulary that only matters inside one package (for example the transformer names in `ai_daily/etl/transformers/`) belongs in that area's `docs/conventions/<area>.md`, not the glossary. Never create a `CONTEXT.md` or `CONTEXT-MAP.md`.
