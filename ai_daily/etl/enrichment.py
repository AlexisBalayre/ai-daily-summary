"""Article enrichment processor."""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

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
