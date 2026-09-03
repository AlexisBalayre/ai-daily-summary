# ADR Format

ADRs live in `docs/adr/` and use sequential numbering: `0001-slug.md`, `0002-slug.md`, etc.

This repo has no `docs/adr/` directory yet; it is created on the first ADR. Until then, design rationale lives in the dated design docs under `docs/design/`. Check those before opening an ADR that would restate one, and notice when a doc has been overtaken (`docs/design/2026-02-07-article-enrichment.md` still describes a separate enrichment job; enrichment now runs inline per `docs/conventions/etl.md`, and that reversal is exactly the kind of decision an ADR would capture).

## Template

```md
# {Short title of the decision}

{1-3 sentences: what's the context, what did we decide, and why.}
```

That's it. An ADR can be a single paragraph. The value is in recording *that* a decision was made and *why*, not in filling out sections.

## Optional sections

Only include these when they add genuine value. Most ADRs won't need them.

- **Status** frontmatter (`proposed | accepted | deprecated | superseded by ADR-NNNN`): useful when decisions are revisited
- **Considered Options**: only when the rejected alternatives are worth remembering
- **Consequences**: only when non-obvious downstream effects need to be called out

## Numbering

Scan `docs/adr/` on `origin/master` (`git ls-tree origin/master docs/adr/` after a fetch) for the highest existing number and increment by one; if the directory does not exist yet, start at `0001`. The local listing goes stale and concurrent merges claim numbers.

## When to offer an ADR

All three of these must be true:

1. **Hard to reverse**: the cost of changing your mind later is meaningful
2. **Surprising without context**: a future reader will look at the code and wonder "why on earth did they do it this way?"
3. **The result of a real trade-off**: there were genuine alternatives and you picked one for specific reasons

If a decision is easy to reverse, skip it; you'll just reverse it. If it's not surprising, nobody will wonder why. If there was no real alternative, there's nothing to record beyond "we did the obvious thing."

### What qualifies

- **Architectural shape.** "Enrichment runs inline during ETL, not as a separate job." "Articles and their embeddings live in one Postgres table with pgvector, not a separate vector store."
- **Integration patterns between areas.** "Outputs consume the enriched `summary`/`category` columns; they never call the LLM themselves."
- **Technology choices that carry lock-in.** Database (PostgreSQL + pgvector), LLM/embedding provider (Gemini vs Ollama), scheduler, deployment target. Not every library, just the ones that would take a quarter to swap out.
- **Boundary and scope decisions.** "Extractors return `RawContent` and never touch the DB or the LLM." The explicit no-s are as valuable as the yes-s.
- **Deliberate deviations from the obvious path.** "Semantic dedup reuses the stored embedding instead of re-embedding because X." Anything where a reasonable reader would assume the opposite. These stop the next engineer from "fixing" something that was deliberate.
- **Constraints not visible in the code.** "The newsletter must send before 08:00 local because that is when subscribers read it." "Gemini free-tier rate limits cap the enrichment batch size."
- **Rejected alternatives when the rejection is non-obvious.** If you considered a separate enrichment job and picked inline enrichment for subtle reasons, record it; otherwise someone will suggest the separate job again in six months.
