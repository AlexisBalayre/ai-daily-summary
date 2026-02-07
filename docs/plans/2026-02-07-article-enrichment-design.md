# Article Enrichment Pipeline Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enrich ingested articles with LLM-generated metadata (summary, category, tags) and detect duplicates via semantic similarity.

**Architecture:** Post-ingestion batch processing. ETL ingests raw articles quickly, then a separate enrichment job processes unenriched articles with LLM classification and embedding-based deduplication.

**Tech Stack:** Google Gemini (LLM + embeddings), pgvector (similarity search), existing orchestrator

---

## Problem Statement

The RSS pipeline currently has three issues:
1. **Missing enrichment** - No summary, categories, or tags on articles
2. **Off-topic content** - General tech feeds include non-AI news
3. **Duplicates** - Same story from multiple feeds

## Solution Overview

A dedicated enrichment job that runs after ETL:
1. Finds articles with `enriched_at IS NULL`
2. Generates embedding, checks for semantic duplicates
3. Calls LLM to classify and summarize
4. Updates article with enrichment data

## Database Schema Changes

New fields on Article model:

```python
class Article(Base):
    # ... existing fields ...

    # Enrichment fields
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_ai_related: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    enriched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("articles.id"), nullable=True)

    # Existing but now actively used
    tags: Mapped[Optional[List[str]]] = mapped_column(ARRAY(Text), nullable=True)
    embedding: Mapped[Optional[List[float]]] = mapped_column(Vector(768), nullable=True)
```

## Enrichment Job Flow

```python
class EnrichmentProcessor:
    BATCH_SIZE = 50
    SIMILARITY_THRESHOLD = 0.92
    LOOKBACK_DAYS = 7

    async def run(self) -> EnrichmentStats:
        articles = get_unenriched_articles(limit=self.BATCH_SIZE)

        for article in articles:
            # Generate embedding
            embedding = await generate_embedding(article.content)

            # Check for duplicates
            duplicate = find_duplicate(article, embedding)
            if duplicate:
                mark_as_duplicate(article, duplicate.id)
                continue

            # LLM enrichment
            enrichment = await llm_enrich(article.title, article.content)

            # Update article
            update_article(article, embedding, enrichment)

        return stats
```

## LLM Enrichment Prompt

```python
ENRICHMENT_PROMPT = """Analyze this tech news article and provide:

1. CATEGORY: One of: ai, security, cloud, hardware, mobile, software, business, other
2. IS_AI_RELATED: true/false - Is this primarily about AI, machine learning, LLMs, or related technology?
3. SUMMARY: 2-3 sentence summary of the key points
4. TAGS: 3-5 relevant tags (lowercase, hyphenated)

Article Title: {title}

Article Content:
{content}

Respond in JSON format:
{{
  "category": "ai",
  "is_ai_related": true,
  "summary": "...",
  "tags": ["llm", "openai", "gpt-4"]
}}"""
```

## Duplicate Detection

Two-layer deduplication:

1. **Content hash** (existing) - Exact duplicates during ingestion
2. **Semantic similarity** (new) - Same story from different sources

```python
def find_duplicate(article: Article, embedding: List[float]) -> Optional[Article]:
    stmt = select(Article).where(
        Article.enriched_at >= datetime.utcnow() - timedelta(days=LOOKBACK_DAYS),
        Article.embedding.isnot(None),
        Article.id != article.id,
        Article.is_duplicate == False,
    ).order_by(
        Article.embedding.cosine_distance(embedding)
    ).limit(1)

    match = db.execute(stmt).scalar_one_or_none()

    if match:
        similarity = 1 - cosine_distance(embedding, match.embedding)
        if similarity >= SIMILARITY_THRESHOLD:
            return match

    return None
```

## Orchestrator Integration

Schedule: 30 minutes after ETL (ETL at :00, enrichment at :30)

```python
enrichment_schedule: str = "30 */4 * * *"
```

CLI command:
```bash
uv run ai-daily run enrichment
```

## File Structure

```
ai_daily/
├── etl/
│   └── enrichment.py          # NEW: EnrichmentProcessor class
├── db/
│   └── models.py              # MODIFY: Add enrichment fields
├── orchestrator/
│   └── jobs.py                # MODIFY: Add run_enrichment job
├── config.py                  # MODIFY: Add enrichment_schedule
└── cli.py                     # MODIFY: Add 'enrichment' to run command
```

## Implementation Tasks

1. Schema migration - Add enrichment fields to Article
2. EnrichmentProcessor - Core enrichment logic
3. Orchestrator integration - Schedule + job registration
4. CLI command - `ai-daily run enrichment`
5. Dashboard updates - Filter by AI-related, show enrichment stats

## Behavior Summary

- ETL ingests raw articles (fast, no LLM calls)
- Enrichment job runs 30min later, processes batch of 50
- Duplicates detected via embedding similarity, marked but kept
- Non-AI articles marked `is_ai_related=false`, kept but filtered from newsletter
- Newsletter uses only `is_ai_related=true` articles
