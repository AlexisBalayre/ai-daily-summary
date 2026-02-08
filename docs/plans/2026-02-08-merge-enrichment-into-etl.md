# Merge Enrichment Into ETL Pipeline

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate the separate enrichment cron job by running LLM enrichment inline during the ETL pipeline, reusing already-generated embeddings to cut redundant API calls.

**Architecture:** The ETL pipeline already generates embeddings for every article. Currently, the enrichment job runs 30 min later and regenerates those same embeddings. We merge the enrichment step (semantic dedup check + LLM classification) into the ETL pipeline right after article creation, reusing the existing embedding. The enrichment scheduler entry and CLI command are removed.

**Tech Stack:** Python, SQLAlchemy, Google Gemini API (genai), pytest

---

### Task 1: Add `enrich_article` method to `EnrichmentProcessor`

Extract the per-article enrichment logic from `_process_batch` into a standalone method that accepts an article and its pre-computed embedding.

**Files:**
- Modify: `ai_daily/etl/enrichment.py:163-219`
- Test: `tests/test_enrichment.py`

**Step 1: Write the failing test**

Add to `tests/test_enrichment.py` at the end of `TestRunAndProcessBatch`:

```python
@pytest.mark.asyncio
async def test_enrich_article_with_precomputed_embedding(self, session):
    """Test enrich_article uses provided embedding instead of generating one."""
    from unittest.mock import AsyncMock, MagicMock, patch
    from ai_daily.etl.enrichment import EnrichmentProcessor

    processor = EnrichmentProcessor()

    mock_article = MagicMock()
    mock_article.id = 1
    mock_article.title = "AI Article"
    mock_article.content = "Content about AI"

    precomputed_embedding = [0.5] * 768

    with patch.object(processor, 'find_duplicate', return_value=None):
        with patch.object(processor, 'llm_enrich', new_callable=AsyncMock, return_value={
            "category": "ai", "is_ai_related": True, "summary": "AI article.", "tags": ["ai"]
        }):
            with patch.object(processor, 'generate_embedding', new_callable=AsyncMock) as mock_embed:
                result = await processor.enrich_article(session, mock_article, precomputed_embedding)

                # Should NOT call generate_embedding since we provided one
                mock_embed.assert_not_called()

    # Article should be enriched
    assert mock_article.category == "ai"
    assert mock_article.is_ai_related is True
    assert mock_article.summary == "AI article."
    assert mock_article.enriched_at is not None
    assert result == "enriched"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_enrichment.py::TestRunAndProcessBatch::test_enrich_article_with_precomputed_embedding -v`
Expected: FAIL with `AttributeError: 'EnrichmentProcessor' object has no attribute 'enrich_article'`

**Step 3: Write implementation**

Add method to `EnrichmentProcessor` in `ai_daily/etl/enrichment.py`:

```python
async def enrich_article(
    self, session: Session, article: Article, embedding: List[float]
) -> str:
    """Enrich a single article using a pre-computed embedding.

    Returns: "enriched", "duplicate", or "error".
    """
    try:
        # Check for semantic duplicates
        duplicate = self.find_duplicate(session, article.id, embedding)
        if duplicate:
            article.is_duplicate = True
            article.duplicate_of_id = duplicate.id
            article.enriched_at = datetime.now(UTC)
            return "duplicate"

        # LLM enrichment
        enrichment = await self.llm_enrich(article.title, article.content)

        article.embedding = embedding
        article.category = enrichment.get("category")
        article.is_ai_related = enrichment.get("is_ai_related", False)
        article.summary = enrichment.get("summary")
        article.tags = enrichment.get("tags", [])
        article.enriched_at = datetime.now(UTC)
        return "enriched"

    except Exception as e:
        logger.error(f"Error enriching article {article.id}: {e}")
        return "error"
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_enrichment.py::TestRunAndProcessBatch::test_enrich_article_with_precomputed_embedding -v`
Expected: PASS

**Step 5: Add test for duplicate detection in enrich_article**

```python
@pytest.mark.asyncio
async def test_enrich_article_detects_duplicate(self, session):
    """Test enrich_article marks duplicates and skips LLM."""
    from unittest.mock import AsyncMock, MagicMock, patch
    from ai_daily.etl.enrichment import EnrichmentProcessor

    processor = EnrichmentProcessor()

    mock_article = MagicMock()
    mock_article.id = 1
    mock_article.title = "Dup Article"
    mock_article.content = "Dup content"

    mock_original = MagicMock()
    mock_original.id = 99

    precomputed_embedding = [0.5] * 768

    with patch.object(processor, 'find_duplicate', return_value=mock_original):
        with patch.object(processor, 'llm_enrich', new_callable=AsyncMock) as mock_llm:
            result = await processor.enrich_article(session, mock_article, precomputed_embedding)
            mock_llm.assert_not_called()

    assert result == "duplicate"
    assert mock_article.is_duplicate is True
    assert mock_article.duplicate_of_id == 99
```

**Step 6: Run all enrichment tests**

Run: `uv run pytest tests/test_enrichment.py -v`
Expected: All PASS

**Step 7: Commit**

```bash
git add ai_daily/etl/enrichment.py tests/test_enrichment.py
git commit -m "feat: add enrich_article method for inline enrichment"
```

---

### Task 2: Integrate enrichment into ETL pipeline

Call `enrich_article` in the ETL pipeline after creating each article, reusing the already-computed embedding.

**Files:**
- Modify: `ai_daily/etl/pipeline.py:49-144`
- Test: `tests/test_pipeline.py` (if exists, otherwise verify via existing tests)

**Step 1: Modify `ETLPipeline.__init__` to include enrichment processor**

In `ai_daily/etl/pipeline.py`, add import and initialization:

```python
# Add to imports at top
from ai_daily.etl.enrichment import EnrichmentProcessor

# In __init__, add:
self.enrichment = EnrichmentProcessor()
```

**Step 2: Add enrichment call after article creation**

In `run_for_source`, after line 139 (`metrics["articles_created"] += 1`), add:

```python
                    # Inline enrichment using already-computed embedding
                    enrich_result = await self.enrichment.enrich_article(session, article, embedding)
                    if enrich_result == "enriched":
                        metrics.setdefault("articles_enriched", 0)
                        metrics["articles_enriched"] += 1
                    elif enrich_result == "duplicate":
                        metrics.setdefault("enrichment_duplicates", 0)
                        metrics["enrichment_duplicates"] += 1
                    elif enrich_result == "error":
                        metrics.setdefault("enrichment_errors", 0)
                        metrics["enrichment_errors"] += 1
```

Also add these keys to the `metrics` dict initialization in `track_job` (line 33):

```python
metrics = {"articles_processed": 0, "articles_created": 0, "duplicates_skipped": 0, "articles_enriched": 0, "enrichment_duplicates": 0, "enrichment_errors": 0}
```

And update `run_all` total_metrics similarly (line 148):

```python
total_metrics = {"articles_processed": 0, "articles_created": 0, "duplicates_skipped": 0, "articles_enriched": 0, "enrichment_duplicates": 0, "enrichment_errors": 0}
```

**Step 3: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add ai_daily/etl/pipeline.py
git commit -m "feat: integrate enrichment into ETL pipeline"
```

---

### Task 3: Remove enrichment from scheduler and CLI

Remove the enrichment cron job, CLI command, and orchestrator job.

**Files:**
- Modify: `ai_daily/config.py:85-87`
- Modify: `ai_daily/orchestrator/jobs.py`
- Modify: `ai_daily/orchestrator/__init__.py`
- Modify: `ai_daily/cli.py`
- Modify: `tests/test_cli_rss.py`

**Step 1: Remove enrichment schedule from config**

In `ai_daily/config.py`, remove lines 85-87:
```python
    enrichment_schedule: str = field(
        default_factory=lambda: os.getenv("ENRICHMENT_SCHEDULE", "30 */4 * * *")
    )
```

**Step 2: Remove `run_enrichment` from orchestrator jobs**

In `ai_daily/orchestrator/jobs.py`:
- Remove the `run_enrichment` function
- Remove `"enrichment": run_enrichment` from the `JOBS` dict

**Step 3: Remove `run_enrichment` from orchestrator `__init__.py`**

In `ai_daily/orchestrator/__init__.py`:
- Remove `run_enrichment` from the import line
- Remove `run_enrichment` from `__all__`

**Step 4: Remove enrichment from CLI**

In `ai_daily/cli.py`:
- Remove `"enrichment"` from the `click.Choice` list in the `run` command
- Remove the enrichment schedule line from the orchestrator schedules dict
- Remove `"enrichment"` from the orchestrator `trigger` command choices if present

**Step 5: Update test**

In `tests/test_cli_rss.py`, remove or update `test_run_enrichment_in_choices` since enrichment is no longer a CLI choice.

**Step 6: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: All PASS

**Step 7: Commit**

```bash
git add ai_daily/config.py ai_daily/orchestrator/jobs.py ai_daily/orchestrator/__init__.py ai_daily/cli.py tests/test_cli_rss.py
git commit -m "feat: remove standalone enrichment job (now merged into ETL)"
```

---

### Task 4: Update CLAUDE.md and verify

Update documentation to reflect the new architecture.

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Update scheduled jobs table**

Remove the enrichment row from the scheduled jobs table and add a note about inline enrichment.

**Step 2: Update ETL Pipeline Flow**

Update the architecture diagram to show enrichment as part of the ETL flow, not a separate step.

**Step 3: Update Common Commands**

Remove `uv run ai-daily run enrichment` from the commands list.

**Step 4: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All 104+ tests PASS

**Step 5: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update architecture to reflect merged enrichment"
```
