# Glossary Format

The domain language lives in one file, `docs/glossary.md`. There is no `CONTEXT.md` or `CONTEXT-MAP.md` in this repo, and no per-context glossaries: every term goes in that one table.

## Structure

```md
| Term            | Meaning |
| :-------------- | :------ |
| **Source**      | A configured place articles come from (a Gmail newsletter sender, an RSS feed, GitHub trending, a crawled site). Rows in `sources`; each has a `type` that selects its extractor. _Avoid_: feed (that is only the RSS kind), provider, channel |
| **Article**     | One normalized, deduplicated item stored in `articles`, carrying its enrichment (`summary`, `category`, `is_ai_related`, embedding). _Avoid_: item, entry, post |
| **RawContent**  | What an extractor returns before transformation: unstored, unenriched, may still be a duplicate. _Avoid_: article (an Article exists only after storage) |
```

One row per term: the term in bold, then its meaning. Aliases to avoid go at the end of the meaning cell, after `_Avoid_:`.

## Rules

- **Be opinionated.** When multiple words exist for the same concept, pick the best one and list the others under `_Avoid_`.
- **Keep definitions tight.** One or two sentences max. Define what it IS, not what it does.
- **Only include terms specific to this project's domain.** General programming concepts (timeouts, error types, utility patterns) don't belong even if the project uses them extensively. `Extractor`, `enrichment`, `newsletter`, and `briefing` belong; `retry` and `session` do not. Before adding a term, ask: is this a concept unique to this project, or a general programming concept? Only the former belongs.
- **Group terms under subheadings** when natural clusters emerge: split the table into one table per `###` subheading. If all terms belong to a single cohesive area, one table is fine.
- **Keep area-only vocabulary in its area doc.** A term that only matters inside one package (for example the transformer names in `ai_daily/etl/transformers/`) belongs in that area's `docs/conventions/<area>.md`, not the glossary.
