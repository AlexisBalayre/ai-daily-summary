# Outputs Conventions (`ai_daily/outputs/`)

Generates the daily deliverables from enriched Articles: the email newsletter, the GitHub-repos email,
the daily summary, and the TTS audio briefing.

## Use the enrichment the pipeline already computed

The ETL enrichment step produces, per article, an LLM `summary`, a `category`, and `is_ai_related`.
Outputs **must consume those fields** rather than re-deriving them:

- Show `article.summary` (a clean LLM abstract), not `article.content` blind-truncated to N characters.
  Only fall back to a truncated excerpt when `summary` is empty.
- Group by the stored `category`, not by keyword-matching the topic string. Keyword heuristics drift
  from the LLM classification and mislabel articles.

If a needed value isn't on the Article yet, add it at enrichment time (with a migration) — don't
recompute it in the output layer.

## Email HTML

- Always `html.escape()` untrusted text (titles, summaries, facts) before inserting into the template.
- Templates live in `templates/`; load via `config.templates_dir`. Keep a minimal inline fallback
  template so a missing file degrades instead of crashing.
- Build `multipart/alternative` messages with **both** a `text/plain` and a `text/html` part — a
  plain-text alternative improves deliverability and accessibility. Don't ship HTML-only.
- Inline CSS for email-client compatibility (no external stylesheets).

## Sending

- Send per recipient; count successes/failures and log both. One recipient failing must not abort the
  rest (see the existing loop in `newsletter.py`).
- Recipients, sender whitelist, and schedule come from config (`config.get_newsletter_recipients()`,
  `config.json`), never hardcoded.

## Summaries & TTS

- `summary_generator.py` caches a `DailySummary` per day and regenerates only when newer articles exist
  — preserve that cache-invalidation contract.
- On LLM/API failure, degrade **visibly** (`_create_fallback_summary` records the error) — never write a
  silent empty summary that looks successful.
