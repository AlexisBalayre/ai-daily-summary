# ETL Conventions (`ai_daily/etl/`)

The ETL pipeline collects content from sources, normalizes it, and stores enriched Articles.

```
Sources (Gmail/RSS/GitHub/Crawler)
  → Extractors (etl/extractors/)  → RawContent
  → Transformers (etl/transformers/: embedder, llm_parser, deduplicator)
  → Articles in PostgreSQL + pgvector
  → Inline enrichment (etl/enrichment.py: classify, summarize, semantic dedup)
```

## Extractors

- Every source extractor lives in `etl/extractors/<source>.py` and **subclasses `BaseExtractor`**.
  Match the existing extractors (`gmail.py`, `rss.py`, `github.py`, `crawler.py`) — same method
  surface, same return type.
- Extractors return `RawContent` objects; they do **not** touch the DB or call the LLM. Extraction is
  pure I/O + parsing so it can be tested against fixtures.
- Network I/O is `async` (`aiohttp`). Set timeouts from config; never hardcode.
- Be defensive about malformed source data — a single bad feed item must not abort the batch. Log and
  skip, don't crash the run.

## Transformers

- `embedder.py` produces embeddings (Google Gemini), `llm_parser.py` parses articles, `deduplicator.py`
  does content-hash dedup. Keep each transformer single-purpose and composable.
- Embeddings are 768-dim vectors stored on the Article; reuse the precomputed embedding for semantic
  dedup rather than re-embedding.

## Enrichment

- `enrichment.py` runs **inline during ETL** (not a separate job): LLM classification (`is_ai_related`),
  per-article `summary`, `category`, and semantic duplicate detection via existing embeddings.
- Enrichment writes the fields that downstream outputs depend on. If you add an enriched field, update
  the Article model, an Alembic migration, and the output that consumes it.

## Idempotency

Re-running ETL over overlapping windows must not create duplicates — rely on content-hash + semantic
dedup, and upsert semantics, not blind inserts.
