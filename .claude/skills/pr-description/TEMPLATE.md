# House-style PR body

Adaptive: always include `## Summary`; add other sections only when the section-selection table in SKILL.md says so. Lead with user-visible change, then implementation, then reviewer-critical info (migrations, edge cases, testing, deferred work).

## Annotated skeleton

```md
## Summary

<One sentence: what this PR does and why.>

- <Concrete change, user- or API-visible first.>
- <`METHOD /path` for new routes; the CLI command for new CLI surface; the component for frontend.>

## Changes            <!-- only if the approach is non-obvious -->

<Approach + notable decisions. Reference files plainly (`enrichment.py`); don't
narrate every file.>

## Migration          <!-- only if models.py or a migration changed -->

`<revision>_<slug>.py`: <additive nullable column / index / etc.> (<default or
backfill rule>). <Backwards-compat verdict.> `downgrade()` <implemented / not feasible because …>.

## Behaviour          <!-- only if rules/edge cases worth flagging -->

- <Gate, default, schedule, or edge case a reviewer should verify.>

## Testing

- `uv run pytest`: <what the new/updated tests cover>.
- <Manual check, if any: a real `uv run ai-daily run rss`, a rendered email, the dashboard.>

## Notes              <!-- optional asides -->

- <docs-only / no code change / follow-up deferred.>
```

## Example: code PR with a migration

Title:

```
feat(db): store model-release flag on articles for the release radar
```

Body:

```md
## Summary

Lets the newsletter's Release Radar section and the instant-alert email select
model-release articles from a stored flag instead of re-scanning tags at render time.

- `articles.is_model_release` (boolean, default false) set by `EnrichmentProcessor`
  from the LLM classification.
- `newsletter.py` and `summary_generator.py` filter on the column; the tag scan is removed.

## Migration

`a1b2c3d4e5f6_add_is_model_release.py`: additive `articles.is_model_release boolean
NOT NULL DEFAULT false`, backfilled from the existing `model-release` tag in the same
revision. Backwards-compatible. `downgrade()` drops the column.

## Behaviour

- Only the model builder announcing a new model counts; platform availability
  ("X now on Bedrock") stays false, matching the enrichment prompt.

## Testing

- `uv run pytest`: enrichment sets the flag from the JSON response; newsletter groups
  flagged articles under Release Radar; backfill covered by a migration test with the
  SQLite fixture.
- Ran `uv run ai-daily run rss` against two feeds and checked the rendered email by hand.
```

## Example: docs-only PR

Title:

```
docs: describe inline enrichment in the ETL conventions
```

Body:

```md
## Summary

Docs-only. `docs/conventions/etl.md` now explains that enrichment runs inline during
ETL (classify, summarize, semantic dedup) and which Article fields it writes, so the
outputs conventions have something to point at.

## Notes

- No code changes.
- `docs/design/2026-02-07-article-enrichment.md` still describes the original
  separate-job design; left as historical record, not updated.
```
