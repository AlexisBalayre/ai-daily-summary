# Article Enrichment Pipeline - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add post-ingestion enrichment job that classifies articles, generates summaries, and detects duplicates.

**Architecture:** Batch processing job triggered after ETL, using LLM for classification and embeddings for deduplication.

**Tech Stack:** Google Gemini, pgvector, SQLAlchemy, existing orchestrator

---

## Task 1: Database Schema Migration

**Files:**
- Modify: `ai_daily/db/models.py`
- Create: `alembic/versions/xxxx_add_enrichment_fields.py`

**Step 1: Write the test for new Article fields**

```python
# tests/test_enrichment.py
def test_article_has_enrichment_fields():
    """Article model has enrichment fields."""
    from ai_daily.db.models import Article

    # Check field existence
    assert hasattr(Article, 'summary')
    assert hasattr(Article, 'category')
    assert hasattr(Article, 'is_ai_related')
    assert hasattr(Article, 'enriched_at')
    assert hasattr(Article, 'is_duplicate')
    assert hasattr(Article, 'duplicate_of_id')
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_enrichment.py::test_article_has_enrichment_fields -v`
Expected: FAIL - fields don't exist yet

**Step 3: Add enrichment fields to Article model**

```python
# ai_daily/db/models.py - add to Article class after existing fields

    # Enrichment fields
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_ai_related: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    enriched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("articles.id"), nullable=True
    )
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_enrichment.py::test_article_has_enrichment_fields -v`
Expected: PASS

**Step 5: Generate Alembic migration**

Run: `cd .worktrees/article-enrichment && uv run alembic revision --autogenerate -m "add enrichment fields to articles"`

**Step 6: Commit**

```bash
git add ai_daily/db/models.py alembic/versions/*.py tests/test_enrichment.py
git commit -m "feat(db): add enrichment fields to Article model"
```

---

## Task 2: EnrichmentProcessor Core Class

**Files:**
- Create: `ai_daily/etl/enrichment.py`
- Create: `tests/test_enrichment.py` (extend)

**Step 1: Write test for EnrichmentProcessor initialization**

```python
# tests/test_enrichment.py
def test_enrichment_processor_init():
    """EnrichmentProcessor initializes with correct defaults."""
    from ai_daily.etl.enrichment import EnrichmentProcessor

    processor = EnrichmentProcessor()
    assert processor.BATCH_SIZE == 50
    assert processor.SIMILARITY_THRESHOLD == 0.92
    assert processor.LOOKBACK_DAYS == 7
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_enrichment.py::test_enrichment_processor_init -v`
Expected: FAIL - module doesn't exist

**Step 3: Create EnrichmentProcessor skeleton**

```python
# ai_daily/etl/enrichment.py
"""Article enrichment processor."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from ai_daily.db.models import Article

logger = logging.getLogger(__name__)


@dataclass
class EnrichmentStats:
    """Statistics from an enrichment run."""
    processed: int = 0
    duplicates: int = 0
    ai_related: int = 0
    errors: int = 0


class EnrichmentProcessor:
    """Process unenriched articles with LLM classification and deduplication."""

    BATCH_SIZE = 50
    SIMILARITY_THRESHOLD = 0.92
    LOOKBACK_DAYS = 7

    async def run(self) -> EnrichmentStats:
        """Run enrichment on unenriched articles."""
        raise NotImplementedError()
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_enrichment.py::test_enrichment_processor_init -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ai_daily/etl/enrichment.py tests/test_enrichment.py
git commit -m "feat(enrichment): add EnrichmentProcessor skeleton"
```

---

## Task 3: Get Unenriched Articles Query

**Files:**
- Modify: `ai_daily/etl/enrichment.py`
- Extend: `tests/test_enrichment.py`

**Step 1: Write test for get_unenriched_articles**

```python
# tests/test_enrichment.py
def test_get_unenriched_articles(db_session):
    """get_unenriched_articles returns articles without enriched_at."""
    from ai_daily.etl.enrichment import EnrichmentProcessor
    from ai_daily.db.models import Article, Source
    from datetime import datetime

    # Create source
    source = Source(type="rss", name="Test")
    db_session.add(source)
    db_session.flush()

    # Create enriched article
    enriched = Article(
        source_id=source.id,
        title="Enriched",
        content="Content",
        enriched_at=datetime.utcnow()
    )
    # Create unenriched article
    unenriched = Article(
        source_id=source.id,
        title="Unenriched",
        content="Content",
        enriched_at=None
    )
    db_session.add_all([enriched, unenriched])
    db_session.commit()

    processor = EnrichmentProcessor()
    articles = processor.get_unenriched_articles(db_session, limit=10)

    assert len(articles) == 1
    assert articles[0].title == "Unenriched"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_enrichment.py::test_get_unenriched_articles -v`
Expected: FAIL - method doesn't exist

**Step 3: Implement get_unenriched_articles**

```python
# ai_daily/etl/enrichment.py - add method to EnrichmentProcessor

    def get_unenriched_articles(
        self, session: Session, limit: int = None
    ) -> List[Article]:
        """Get articles that haven't been enriched yet."""
        from sqlalchemy import select

        limit = limit or self.BATCH_SIZE
        stmt = (
            select(Article)
            .where(Article.enriched_at.is_(None))
            .where(Article.is_duplicate == False)
            .order_by(Article.ingested_at.desc())
            .limit(limit)
        )
        return list(session.execute(stmt).scalars().all())
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_enrichment.py::test_get_unenriched_articles -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ai_daily/etl/enrichment.py tests/test_enrichment.py
git commit -m "feat(enrichment): add get_unenriched_articles query"
```

---

## Task 4: Embedding Generation

**Files:**
- Modify: `ai_daily/etl/enrichment.py`
- Extend: `tests/test_enrichment.py`

**Step 1: Write test for generate_embedding**

```python
# tests/test_enrichment.py
@pytest.mark.asyncio
async def test_generate_embedding(mocker):
    """generate_embedding returns 768-dim vector."""
    from ai_daily.etl.enrichment import EnrichmentProcessor

    # Mock the embedding API
    mock_embed = mocker.patch('ai_daily.etl.enrichment.embed_text')
    mock_embed.return_value = [0.1] * 768

    processor = EnrichmentProcessor()
    embedding = await processor.generate_embedding("Test content")

    assert len(embedding) == 768
    mock_embed.assert_called_once_with("Test content")
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_enrichment.py::test_generate_embedding -v`
Expected: FAIL - method doesn't exist

**Step 3: Implement generate_embedding**

```python
# ai_daily/etl/enrichment.py - add to EnrichmentProcessor

    async def generate_embedding(self, content: str) -> List[float]:
        """Generate embedding vector for content."""
        from ai_daily.llm import embed_text

        # Truncate to reasonable size for embedding
        truncated = content[:8000]
        return embed_text(truncated)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_enrichment.py::test_generate_embedding -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ai_daily/etl/enrichment.py tests/test_enrichment.py
git commit -m "feat(enrichment): add embedding generation"
```

---

## Task 5: Duplicate Detection

**Files:**
- Modify: `ai_daily/etl/enrichment.py`
- Extend: `tests/test_enrichment.py`

**Step 1: Write test for find_duplicate**

```python
# tests/test_enrichment.py
def test_find_duplicate_returns_match(db_session):
    """find_duplicate returns matching article above threshold."""
    from ai_daily.etl.enrichment import EnrichmentProcessor
    from ai_daily.db.models import Article, Source
    from datetime import datetime

    source = Source(type="rss", name="Test")
    db_session.add(source)
    db_session.flush()

    # Create existing enriched article with embedding
    existing = Article(
        source_id=source.id,
        title="AI News",
        content="Content about AI",
        enriched_at=datetime.utcnow(),
        embedding=[0.1] * 768
    )
    db_session.add(existing)
    db_session.commit()

    processor = EnrichmentProcessor()
    # Very similar embedding (same values)
    similar_embedding = [0.1] * 768

    duplicate = processor.find_duplicate(db_session, existing.id, similar_embedding)
    assert duplicate is not None
    assert duplicate.id == existing.id


def test_find_duplicate_returns_none_below_threshold(db_session):
    """find_duplicate returns None when similarity below threshold."""
    from ai_daily.etl.enrichment import EnrichmentProcessor
    from ai_daily.db.models import Article, Source
    from datetime import datetime

    source = Source(type="rss", name="Test")
    db_session.add(source)
    db_session.flush()

    existing = Article(
        source_id=source.id,
        title="AI News",
        content="Content about AI",
        enriched_at=datetime.utcnow(),
        embedding=[0.1] * 768
    )
    db_session.add(existing)
    db_session.commit()

    processor = EnrichmentProcessor()
    # Very different embedding
    different_embedding = [0.9] * 768

    duplicate = processor.find_duplicate(db_session, 9999, different_embedding)
    assert duplicate is None
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_enrichment.py -k "find_duplicate" -v`
Expected: FAIL

**Step 3: Implement find_duplicate**

```python
# ai_daily/etl/enrichment.py - add to EnrichmentProcessor

    def find_duplicate(
        self, session: Session, article_id: int, embedding: List[float]
    ) -> Optional[Article]:
        """Find a semantically duplicate article."""
        from sqlalchemy import select

        cutoff = datetime.utcnow() - timedelta(days=self.LOOKBACK_DAYS)

        stmt = (
            select(Article)
            .where(Article.enriched_at >= cutoff)
            .where(Article.embedding.isnot(None))
            .where(Article.id != article_id)
            .where(Article.is_duplicate == False)
            .order_by(Article.embedding.cosine_distance(embedding))
            .limit(1)
        )

        match = session.execute(stmt).scalar_one_or_none()

        if match:
            # Calculate similarity (1 - distance)
            from pgvector.sqlalchemy import Vector
            distance = session.execute(
                select(match.embedding.cosine_distance(embedding))
            ).scalar()
            similarity = 1 - distance

            if similarity >= self.SIMILARITY_THRESHOLD:
                return match

        return None
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_enrichment.py -k "find_duplicate" -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ai_daily/etl/enrichment.py tests/test_enrichment.py
git commit -m "feat(enrichment): add duplicate detection via embeddings"
```

---

## Task 6: LLM Enrichment

**Files:**
- Modify: `ai_daily/etl/enrichment.py`
- Extend: `tests/test_enrichment.py`

**Step 1: Write test for llm_enrich**

```python
# tests/test_enrichment.py
@pytest.mark.asyncio
async def test_llm_enrich(mocker):
    """llm_enrich returns parsed enrichment data."""
    from ai_daily.etl.enrichment import EnrichmentProcessor

    mock_llm = mocker.patch('ai_daily.etl.enrichment.generate_text')
    mock_llm.return_value = '''{
        "category": "ai",
        "is_ai_related": true,
        "summary": "This is about AI.",
        "tags": ["llm", "gpt"]
    }'''

    processor = EnrichmentProcessor()
    result = await processor.llm_enrich("AI Title", "AI Content here")

    assert result["category"] == "ai"
    assert result["is_ai_related"] == True
    assert result["summary"] == "This is about AI."
    assert result["tags"] == ["llm", "gpt"]
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_enrichment.py::test_llm_enrich -v`
Expected: FAIL

**Step 3: Implement llm_enrich**

```python
# ai_daily/etl/enrichment.py - add to EnrichmentProcessor

    ENRICHMENT_PROMPT = '''Analyze this tech news article and provide:

1. CATEGORY: One of: ai, security, cloud, hardware, mobile, software, business, other
2. IS_AI_RELATED: true/false - Is this primarily about AI, machine learning, LLMs, or related technology?
3. SUMMARY: 2-3 sentence summary of the key points
4. TAGS: 3-5 relevant tags (lowercase, hyphenated)

Article Title: {title}

Article Content:
{content}

Respond ONLY with valid JSON:
{{"category": "...", "is_ai_related": true/false, "summary": "...", "tags": ["...", "..."]}}'''

    async def llm_enrich(self, title: str, content: str) -> dict:
        """Get LLM enrichment for article."""
        import json
        from ai_daily.llm import generate_text

        # Truncate content
        truncated = content[:4000]

        prompt = self.ENRICHMENT_PROMPT.format(title=title, content=truncated)
        response = generate_text(prompt)

        # Parse JSON from response
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            import re
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                return json.loads(match.group())
            raise ValueError(f"Could not parse LLM response: {response}")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_enrichment.py::test_llm_enrich -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ai_daily/etl/enrichment.py tests/test_enrichment.py
git commit -m "feat(enrichment): add LLM enrichment with prompt"
```

---

## Task 7: Main Run Method

**Files:**
- Modify: `ai_daily/etl/enrichment.py`
- Extend: `tests/test_enrichment.py`

**Step 1: Write test for run method**

```python
# tests/test_enrichment.py
@pytest.mark.asyncio
async def test_enrichment_run(db_session, mocker):
    """run() processes unenriched articles."""
    from ai_daily.etl.enrichment import EnrichmentProcessor
    from ai_daily.db.models import Article, Source

    # Create test data
    source = Source(type="rss", name="Test")
    db_session.add(source)
    db_session.flush()

    article = Article(
        source_id=source.id,
        title="Test Article",
        content="Content about testing",
        enriched_at=None
    )
    db_session.add(article)
    db_session.commit()

    # Mock external calls
    mocker.patch('ai_daily.etl.enrichment.embed_text', return_value=[0.1] * 768)
    mocker.patch('ai_daily.etl.enrichment.generate_text', return_value='''{
        "category": "software",
        "is_ai_related": false,
        "summary": "Test summary",
        "tags": ["testing"]
    }''')

    processor = EnrichmentProcessor()
    stats = await processor.run(db_session)

    assert stats.processed == 1

    # Verify article was enriched
    db_session.refresh(article)
    assert article.enriched_at is not None
    assert article.category == "software"
    assert article.is_ai_related == False
    assert article.summary == "Test summary"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_enrichment.py::test_enrichment_run -v`
Expected: FAIL

**Step 3: Implement run method**

```python
# ai_daily/etl/enrichment.py - replace the run method

    async def run(self, session: Session = None) -> EnrichmentStats:
        """Run enrichment on unenriched articles."""
        from ai_daily.db import get_session

        stats = EnrichmentStats()

        if session is None:
            with get_session() as session:
                return await self._process_batch(session, stats)
        else:
            return await self._process_batch(session, stats)

    async def _process_batch(self, session: Session, stats: EnrichmentStats) -> EnrichmentStats:
        """Process a batch of unenriched articles."""
        articles = self.get_unenriched_articles(session)

        for article in articles:
            try:
                # Generate embedding
                embedding = await self.generate_embedding(article.content)

                # Check for duplicates
                duplicate = self.find_duplicate(session, article.id, embedding)
                if duplicate:
                    article.is_duplicate = True
                    article.duplicate_of_id = duplicate.id
                    article.enriched_at = datetime.utcnow()
                    stats.duplicates += 1
                    continue

                # LLM enrichment
                enrichment = await self.llm_enrich(article.title, article.content)

                # Update article
                article.embedding = embedding
                article.category = enrichment.get("category")
                article.is_ai_related = enrichment.get("is_ai_related", False)
                article.summary = enrichment.get("summary")
                article.tags = enrichment.get("tags", [])
                article.enriched_at = datetime.utcnow()

                stats.processed += 1
                if article.is_ai_related:
                    stats.ai_related += 1

            except Exception as e:
                logger.error(f"Error enriching article {article.id}: {e}")
                stats.errors += 1

        session.commit()
        return stats
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_enrichment.py::test_enrichment_run -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ai_daily/etl/enrichment.py tests/test_enrichment.py
git commit -m "feat(enrichment): implement main run method"
```

---

## Task 8: CLI Command

**Files:**
- Modify: `ai_daily/cli.py`
- Extend: `tests/test_enrichment.py`

**Step 1: Write test for CLI command**

```python
# tests/test_enrichment.py
def test_cli_run_enrichment_in_choices():
    """'enrichment' is a valid choice for run command."""
    from ai_daily.cli import cli
    from click.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(cli, ['run', '--help'])
    assert 'enrichment' in result.output
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_enrichment.py::test_cli_run_enrichment_in_choices -v`
Expected: FAIL

**Step 3: Add 'enrichment' to CLI run command**

Modify `ai_daily/cli.py`:
- Add 'enrichment' to the run command choices
- Add handler for enrichment job

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_enrichment.py::test_cli_run_enrichment_in_choices -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ai_daily/cli.py tests/test_enrichment.py
git commit -m "feat(cli): add 'enrichment' to run command"
```

---

## Task 9: Orchestrator Integration

**Files:**
- Modify: `ai_daily/config.py`
- Modify: `ai_daily/orchestrator/jobs.py`

**Step 1: Add enrichment_schedule to config**

```python
# ai_daily/config.py - add to OrchestratorConfig
    enrichment_schedule: str = field(
        default_factory=lambda: os.getenv("ENRICHMENT_SCHEDULE", "30 */4 * * *")
    )
```

**Step 2: Add run_enrichment job**

```python
# ai_daily/orchestrator/jobs.py
async def run_enrichment():
    """Enrich unenriched articles with LLM-generated metadata."""
    from ai_daily.etl.enrichment import EnrichmentProcessor

    processor = EnrichmentProcessor()
    stats = await processor.run()

    return {
        "processed": stats.processed,
        "duplicates": stats.duplicates,
        "ai_related": stats.ai_related,
        "errors": stats.errors,
    }
```

**Step 3: Register job in scheduler**

Add enrichment to the jobs dict in the scheduler.

**Step 4: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add ai_daily/config.py ai_daily/orchestrator/jobs.py
git commit -m "feat(orchestrator): add enrichment job scheduling"
```

---

## Task 10: Final Integration Test

**Files:**
- Extend: `tests/test_enrichment.py`

**Step 1: Write integration test**

```python
# tests/test_enrichment.py
@pytest.mark.asyncio
async def test_enrichment_full_pipeline(db_session, mocker):
    """Full enrichment pipeline processes and deduplicates articles."""
    from ai_daily.etl.enrichment import EnrichmentProcessor
    from ai_daily.db.models import Article, Source

    source = Source(type="rss", name="Test")
    db_session.add(source)
    db_session.flush()

    # Create two similar articles (should be deduplicated)
    article1 = Article(source_id=source.id, title="AI News 1", content="Content about AI advances")
    article2 = Article(source_id=source.id, title="AI News 2", content="Content about AI advances")  # duplicate
    article3 = Article(source_id=source.id, title="Security News", content="Content about security")
    db_session.add_all([article1, article2, article3])
    db_session.commit()

    # Mock: first two get same embedding (duplicates), third is different
    embed_calls = [0]
    def mock_embed(text):
        embed_calls[0] += 1
        if embed_calls[0] <= 2:
            return [0.1] * 768
        return [0.9] * 768

    mocker.patch('ai_daily.etl.enrichment.embed_text', side_effect=mock_embed)

    llm_calls = [0]
    def mock_llm(prompt):
        llm_calls[0] += 1
        if "AI" in prompt:
            return '{"category": "ai", "is_ai_related": true, "summary": "AI summary", "tags": ["ai"]}'
        return '{"category": "security", "is_ai_related": false, "summary": "Security summary", "tags": ["security"]}'

    mocker.patch('ai_daily.etl.enrichment.generate_text', side_effect=mock_llm)

    processor = EnrichmentProcessor()
    stats = await processor.run(db_session)

    assert stats.processed == 2  # article1 and article3
    assert stats.duplicates == 1  # article2
    assert stats.ai_related == 1  # only article1
```

**Step 2: Run integration test**

Run: `uv run pytest tests/test_enrichment.py::test_enrichment_full_pipeline -v`
Expected: PASS

**Step 3: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add tests/test_enrichment.py
git commit -m "test(enrichment): add integration test"
```
