"""Article enrichment processor."""

import json
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from google import genai
from google.genai.types import GenerateContentConfig
from sqlalchemy.orm import Session

from ai_daily.config import config
from ai_daily.db.models import Article
from ai_daily.etl.transformers.embedder import Embedder

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

    ENRICHMENT_PROMPT = """Analyze this tech news article and provide:

1. CATEGORY: One of: ai, security, cloud, hardware, mobile, software, business, other
2. IS_AI_RELATED: true/false - Is this primarily about AI, machine learning, LLMs, or related technology?
3. IS_MODEL_RELEASE: true/false - True ONLY when the article's primary news is the organization that BUILT an AI model announcing that NEW model or a major new version (e.g. "Introducing Claude Sonnet 5", "GPT-5.6 is here", a new TTS/STT/speech or open-weight model). False for everything else, including: a platform adding support/availability/fine-tuning for an EXISTING model (e.g. "Fine-tune X on SageMaker", "X now available on Bedrock/Azure"), product features built on top of models, memory/context upgrades to an app, API/tooling changes, benchmarks, tutorials, case studies, opinion, or funding news.
4. SUMMARY: 2-3 sentence summary of the key points
5. TAGS: 3-5 relevant tags (lowercase, hyphenated)

Article Title: {title}

Article Content:
{content}

Respond ONLY with valid JSON:
{{"category": "...", "is_ai_related": true/false, "is_model_release": true/false, "summary": "...", "tags": ["...", "..."]}}"""

    # Tag used to mark model-release articles (drives the newsletter Release Radar
    # and the instant-alert email). Stored in the existing tags array — no migration.
    MODEL_RELEASE_TAG = "model-release"

    def __init__(self):
        """Initialize the enrichment processor."""
        self._embedder: Embedder | None = None

    @property
    def embedder(self) -> Embedder:
        """Lazy initialization of embedder."""
        if self._embedder is None:
            self._embedder = Embedder()
        return self._embedder

    async def generate_embedding(self, content: str) -> list[float]:
        """Generate embedding vector for content.

        Args:
            content: Text content to generate embedding for.

        Returns:
            Vector embedding as list of floats.
        """
        return await self.embedder.embed(content)

    async def llm_enrich(self, title: str, content: str) -> dict:
        """Get LLM enrichment for article.

        Args:
            title: Article title.
            content: Article content.

        Returns:
            Dict with keys: category, is_ai_related, summary, tags.

        Raises:
            ValueError: If LLM response cannot be parsed as JSON.
        """
        # Truncate content to save tokens
        truncated = content[:4000]

        prompt = self.ENRICHMENT_PROMPT.format(title=title, content=truncated)

        # Use existing LLM infrastructure
        client = genai.Client(api_key=config.llm.google_api_key)
        response = await client.aio.models.generate_content(
            model=config.llm.model,
            contents=prompt,
            config=GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )

        # Parse JSON from response
        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            match = re.search(r"\{.*\}", response.text, re.DOTALL)
            if match:
                return json.loads(match.group())
            raise ValueError(f"Could not parse LLM response: {response.text}") from None

    def get_unenriched_articles(self, session: Session, limit: int = None) -> list[Article]:
        """Get articles that haven't been enriched yet."""
        from sqlalchemy import select

        limit = limit or self.BATCH_SIZE
        stmt = (
            select(Article)
            .where(Article.enriched_at.is_(None))
            .where(Article.is_duplicate.is_(False))
            .order_by(Article.ingested_at.desc())
            .limit(limit)
        )
        return list(session.execute(stmt).scalars().all())

    def find_duplicate(
        self, session: Session, article_id: int, embedding: list[float]
    ) -> Article | None:
        """Find a semantically duplicate article.

        Returns the duplicate article if similarity >= SIMILARITY_THRESHOLD,
        otherwise returns None.
        """
        from sqlalchemy import select

        cutoff = datetime.now(UTC) - timedelta(days=self.LOOKBACK_DAYS)

        # Query for the most similar article using pgvector cosine distance
        stmt = (
            select(Article)
            .where(Article.enriched_at >= cutoff)
            .where(Article.embedding.isnot(None))
            .where(Article.id != article_id)
            .where(Article.is_duplicate.is_(False))
            .order_by(Article.embedding.cosine_distance(embedding))
            .limit(1)
        )

        match = session.execute(stmt).scalar_one_or_none()

        if match:
            # Calculate similarity (1 - cosine_distance)
            # For pgvector, cosine_distance returns distance, not similarity
            distance_stmt = select(Article.embedding.cosine_distance(embedding)).where(
                Article.id == match.id
            )
            distance = session.execute(distance_stmt).scalar()
            similarity = 1 - distance

            if similarity >= self.SIMILARITY_THRESHOLD:
                return match

        return None

    async def enrich_article(
        self, session: Session, article: Article, embedding: list[float]
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
            tags = list(enrichment.get("tags", []) or [])
            if enrichment.get("is_model_release") and self.MODEL_RELEASE_TAG not in tags:
                tags.append(self.MODEL_RELEASE_TAG)
            article.tags = tags
            article.enriched_at = datetime.now(UTC)
            return "enriched"

        except Exception as e:
            logger.error(f"Error enriching article {article.id}: {e}")
            return "error"

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

        logger.info(f"Processing {len(articles)} unenriched articles")

        for article in articles:
            try:
                # Generate embedding
                embedding = await self.generate_embedding(article.content)

                # Check for duplicates
                duplicate = self.find_duplicate(session, article.id, embedding)
                if duplicate:
                    article.is_duplicate = True
                    article.duplicate_of_id = duplicate.id
                    article.enriched_at = datetime.now(UTC)
                    stats.duplicates += 1
                    logger.debug(f"Article {article.id} marked as duplicate of {duplicate.id}")
                    continue

                # LLM enrichment
                enrichment = await self.llm_enrich(article.title, article.content)

                # Update article
                article.embedding = embedding
                article.category = enrichment.get("category")
                article.is_ai_related = enrichment.get("is_ai_related", False)
                article.summary = enrichment.get("summary")
                article.tags = enrichment.get("tags", [])
                article.enriched_at = datetime.now(UTC)

                stats.processed += 1
                if article.is_ai_related:
                    stats.ai_related += 1

                logger.debug(
                    f"Enriched article {article.id}: category={article.category}, ai_related={article.is_ai_related}"
                )

            except Exception as e:
                logger.error(f"Error enriching article {article.id}: {e}")
                stats.errors += 1

        session.commit()
        logger.info(
            f"Enrichment complete: {stats.processed} processed, {stats.duplicates} duplicates, {stats.ai_related} AI-related, {stats.errors} errors"
        )
        return stats
