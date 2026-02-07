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

    async def run(self, session: Session = None) -> EnrichmentStats:
        """Run enrichment on unenriched articles."""
        raise NotImplementedError()
