"""Content deduplication using hash and semantic similarity."""

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_daily.db.models import Article


def compute_content_hash(title: str, content: str) -> str:
    """Compute MD5 hash of title + content prefix."""
    text = f"{title}{content[:200]}"
    return hashlib.md5(text.encode()).hexdigest()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0

    dot_product = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)


class Deduplicator:
    """Check for duplicate content using hash and embedding similarity."""

    SIMILARITY_THRESHOLD = 0.92

    def __init__(self, session: Session):
        self.session = session

    def is_duplicate_by_hash(self, content_hash: str) -> bool:
        """Check if content hash already exists."""
        stmt = select(Article.id).where(Article.content_hash == content_hash).limit(1)
        result = self.session.execute(stmt).first()
        return result is not None

    def is_duplicate_by_external_id(self, source_id: int, external_id: str) -> bool:
        """Check if external ID already exists for this source."""
        stmt = (
            select(Article.id)
            .where(Article.source_id == source_id, Article.external_id == external_id)
            .limit(1)
        )
        result = self.session.execute(stmt).first()
        return result is not None

    def find_similar_by_embedding(
        self, embedding: list[float], limit: int = 5
    ) -> list[tuple[int, float]]:
        """Find similar articles by embedding.

        Note: For production, use pgvector's built-in similarity search.
        This is a fallback implementation.

        Returns:
            List of (article_id, similarity_score) tuples.
        """
        stmt = select(Article).where(Article.embedding.isnot(None)).limit(100)
        articles = self.session.execute(stmt).scalars().all()

        similarities = []
        for article in articles:
            if article.embedding is not None:
                sim = cosine_similarity(embedding, list(article.embedding))
                if sim >= self.SIMILARITY_THRESHOLD:
                    similarities.append((article.id, sim))

        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:limit]

    def is_duplicate(
        self,
        source_id: int,
        external_id: str,
        content_hash: str,
        embedding: list[float] | None = None,
    ) -> tuple[bool, int | None]:
        """Check if content is duplicate.

        Args:
            source_id: Source ID.
            external_id: External ID from source.
            content_hash: MD5 hash of content.
            embedding: Optional embedding for semantic dedup.

        Returns:
            Tuple of (is_duplicate, related_article_id).
        """
        if self.is_duplicate_by_external_id(source_id, external_id):
            return True, None

        if self.is_duplicate_by_hash(content_hash):
            return True, None

        if embedding is not None:
            similar = self.find_similar_by_embedding(embedding, limit=1)
            if similar:
                return True, similar[0][0]

        return False, None
