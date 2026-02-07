"""Article enrichment processor."""

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

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

    def __init__(self):
        """Initialize the enrichment processor."""
        self._embedder: Optional[Embedder] = None

    @property
    def embedder(self) -> Embedder:
        """Lazy initialization of embedder."""
        if self._embedder is None:
            self._embedder = Embedder()
        return self._embedder

    async def generate_embedding(self, content: str) -> List[float]:
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
            match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if match:
                return json.loads(match.group())
            raise ValueError(f"Could not parse LLM response: {response.text}")

    def get_unenriched_articles(self, session: Session, limit: int = None) -> List[Article]:
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

    def find_duplicate(
        self, session: Session, article_id: int, embedding: List[float]
    ) -> Optional[Article]:
        """Find a semantically duplicate article.

        Returns the duplicate article if similarity >= SIMILARITY_THRESHOLD,
        otherwise returns None.
        """
        from sqlalchemy import select

        cutoff = datetime.utcnow() - timedelta(days=self.LOOKBACK_DAYS)

        # Query for the most similar article using pgvector cosine distance
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
            # Calculate similarity (1 - cosine_distance)
            # For pgvector, cosine_distance returns distance, not similarity
            distance_stmt = select(Article.embedding.cosine_distance(embedding)).where(Article.id == match.id)
            distance = session.execute(distance_stmt).scalar()
            similarity = 1 - distance

            if similarity >= self.SIMILARITY_THRESHOLD:
                return match

        return None

    async def run(self, session: Session = None) -> EnrichmentStats:
        """Run enrichment on unenriched articles."""
        raise NotImplementedError()
