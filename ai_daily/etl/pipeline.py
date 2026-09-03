"""ETL Pipeline orchestrator."""

import logging
from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from ai_daily.db import Article, JobRun, Source, get_session
from ai_daily.etl.enrichment import EnrichmentProcessor
from ai_daily.etl.extractors import (
    BaseExtractor,
    CrawlerExtractor,
    GitHubExtractor,
    GmailExtractor,
    RSSExtractor,
)
from ai_daily.etl.transformers import Deduplicator, Embedder, LLMParser, compute_content_hash

logger = logging.getLogger(__name__)


EXTRACTORS: dict[str, type[BaseExtractor]] = {
    "newsletter": GmailExtractor,
    "github": GitHubExtractor,
    "crawler": CrawlerExtractor,
    "rss": RSSExtractor,
}


@contextmanager
def track_job(session: Session, job_name: str):
    """Context manager for tracking job execution."""
    job = JobRun(job_name=job_name, status="running")
    session.add(job)
    session.commit()

    metrics = {
        "articles_processed": 0,
        "articles_created": 0,
        "duplicates_skipped": 0,
        "articles_enriched": 0,
        "enrichment_duplicates": 0,
        "enrichment_errors": 0,
    }

    try:
        yield job, metrics
        job.status = "success"
        job.metrics = metrics
    except Exception as e:
        job.status = "failed"
        job.error_message = str(e)
        job.metrics = metrics
        raise
    finally:
        job.finished_at = datetime.now(UTC)
        session.commit()


class ETLPipeline:
    """Main ETL pipeline orchestrator."""

    def __init__(self):
        self.extractors: dict[str, BaseExtractor] = {}
        self.llm_parser = LLMParser()
        self.embedder = Embedder()
        self.enrichment = EnrichmentProcessor()

    def _get_extractor(self, source_type: str) -> BaseExtractor:
        """Get or create extractor for source type."""
        if source_type not in self.extractors:
            extractor_class = EXTRACTORS.get(source_type)
            if not extractor_class:
                raise ValueError(f"No extractor for source type: {source_type}")
            self.extractors[source_type] = extractor_class()
        return self.extractors[source_type]

    async def run_for_source(self, source: Source, session: Session) -> dict:
        """Run ETL pipeline for a single source."""
        job_name = f"etl_{source.type}_{source.id}"

        with track_job(session, job_name) as (job, metrics):
            extractor = self._get_extractor(source.type)
            raw_contents = await extractor.extract(source)
            logger.info(f"Extracted {len(raw_contents)} items from {source.name}")

            deduplicator = Deduplicator(session)

            for raw in raw_contents:
                metrics["articles_processed"] += 1

                if source.type == "newsletter":
                    articles_data = await self.llm_parser.parse(raw)
                else:
                    articles_data = [
                        {
                            "title": raw.title,
                            "content": raw.content,
                            "topic": "AI Products, Tools, and Repositories"
                            if source.type == "github"
                            else "Industry News and Trends",
                            "url": raw.url,
                            "source_name": raw.source_name,
                            "external_id": raw.external_id,
                        }
                    ]

                for article_data in articles_data:
                    if not article_data.get("title") or not article_data.get("content"):
                        logger.warning(
                            f"Skipping article with missing title/content from {source.name}"
                        )
                        continue

                    content_hash = compute_content_hash(
                        article_data["title"], article_data["content"]
                    )

                    is_dup, related_id = deduplicator.is_duplicate(
                        source_id=source.id,
                        external_id=article_data.get("external_id", raw.external_id),
                        content_hash=content_hash,
                    )

                    if is_dup:
                        metrics["duplicates_skipped"] += 1
                        continue

                    embed_text = f"{article_data['title']} {article_data['content']}"
                    embedding = await self.embedder.embed(embed_text)

                    is_dup, related_id = deduplicator.is_duplicate(
                        source_id=source.id,
                        external_id=article_data.get("external_id", raw.external_id),
                        content_hash=content_hash,
                        embedding=embedding,
                    )

                    if is_dup:
                        metrics["duplicates_skipped"] += 1
                        continue

                    article = Article(
                        source_id=source.id,
                        external_id=article_data.get("external_id", raw.external_id),
                        title=article_data["title"],
                        content=article_data["content"],
                        url=article_data.get("url"),
                        author=raw.author,
                        published_at=raw.published_at,
                        topic=article_data.get("topic"),
                        embedding=embedding,
                        content_hash=content_hash,
                    )
                    session.add(article)
                    session.flush()
                    metrics["articles_created"] += 1

                    # Inline enrichment using already-computed embedding
                    enrich_result = await self.enrichment.enrich_article(
                        session, article, embedding
                    )
                    if enrich_result == "enriched":
                        metrics["articles_enriched"] += 1
                    elif enrich_result == "duplicate":
                        metrics["enrichment_duplicates"] += 1
                    elif enrich_result == "error":
                        metrics["enrichment_errors"] += 1

            session.commit()
            logger.info(
                f"Created {metrics['articles_created']} articles, skipped {metrics['duplicates_skipped']} duplicates"
            )

        return metrics

    async def run_all(self, source_types: list[str] | None = None) -> dict:
        """Run ETL for all enabled sources."""
        total_metrics = {
            "articles_processed": 0,
            "articles_created": 0,
            "duplicates_skipped": 0,
            "articles_enriched": 0,
            "enrichment_duplicates": 0,
            "enrichment_errors": 0,
        }

        with get_session() as session:
            query = session.query(Source).filter(Source.enabled.is_(True))
            if source_types:
                query = query.filter(Source.type.in_(source_types))

            sources = query.all()

            for source in sources:
                try:
                    metrics = await self.run_for_source(source, session)
                    for key in total_metrics:
                        total_metrics[key] += metrics.get(key, 0)
                except Exception as e:
                    logger.error(f"Error processing source {source.name}: {e}")

        return total_metrics
