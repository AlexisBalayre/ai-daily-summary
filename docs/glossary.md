# Glossary

The shared vocabulary. Names in code, docs, and conversation should match these exactly.
When a term is fuzzy, sharpen it here first.

| Term | Meaning |
| :--- | :------ |
| **Source** | A configured content origin (`gmail`, `rss`, `github`, `crawler`) with its JSON config and an `enabled` flag; `Source` model. |
| **Extractor** | The `BaseExtractor` subclass that fetches items for one source type. |
| **RawContent** | The unsaved item an extractor yields (`ai_daily/etl/types.py`), before it becomes an Article. |
| **Article** | One stored news item, with its enrichment fields and embedding; `Article` model. |
| **Enrichment** | The inline ETL step that sets an Article's `summary`, `category`, `is_ai_related`, `tags` and `embedding`, and marks semantic duplicates. Outputs consume these fields rather than re-deriving them. |
| **Duplicate** | An Article flagged `is_duplicate` with `duplicate_of_id`: exact via `content_hash`, or semantic via embedding similarity. |
| **Whitelist** | The Gmail sender addresses whose mail is ingested; `config.json` wins over the Source row's config. |
| **Model release** | An Article enrichment tagged `model-release`; drives the newsletter's Release Radar and instant alerts. |
| **DailySummary** | The generated summary of one day's Articles, stored per date; `DailySummary` model. |
| **Newsletter** | The daily HTML email built from enriched Articles, sent to `RECIPIENTS`. |
| **Briefing** | The spoken audio version of the daily summary, produced with Pocket TTS. |
| **Leaderboard snapshot** | A captured state of a public model leaderboard, diffed against the previous one; `LeaderboardSnapshot` model. |
| **Job** | A named orchestrator task (`etl`, `newsletter`, `github`, `leaderboards`, `tts`) run on a cron schedule with retries. |
| **JobRun** | The persisted record of one job execution and its outcome; `JobRun` model. |

> The `domain-modeling` skill (which `grill-with-docs` delegates to) and the
> `improve-codebase-architecture` skill both read this glossary to keep naming consistent.
> Vocabulary that matters only inside one area belongs in that area's `docs/conventions/<area>.md`.
