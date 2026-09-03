"""Generate daily summaries from articles."""

import json
import logging
from datetime import UTC, date, datetime, timedelta

from google import genai
from google.genai.types import GenerateContentConfig
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ai_daily.config import config
from ai_daily.db import Article, DailySummary

logger = logging.getLogger(__name__)


class SummaryGenerator:
    """Generate daily summaries using LLM."""

    SYSTEM_PROMPT = """You are an expert AI news summarizer.

Given today's articles, create:
1. A concise summary (2-3 paragraphs) of the key developments
2. A list of the most important facts (5-10 bullet points)

Focus on:
- AI Research breakthroughs
- New tools and products
- Industry trends
- Notable data science techniques

Output valid JSON:
{
    "summary": "...",
    "key_facts": ["...", "..."]
}"""

    def __init__(self):
        self.client = genai.Client(api_key=config.llm.google_api_key)
        self.model = config.llm.model

    def get_cached_summary(self, session: Session, target_date: date) -> DailySummary | None:
        """Get cached summary for date if exists."""
        stmt = select(DailySummary).where(
            DailySummary.date == datetime.combine(target_date, datetime.min.time(), tzinfo=UTC)
        )
        return session.execute(stmt).scalar_one_or_none()

    def get_recent_articles(self, session: Session, hours: int = 24) -> list[Article]:
        """Get articles from the last N hours."""
        cutoff = datetime.now(UTC) - timedelta(hours=hours)

        stmt = (
            select(Article)
            .where(
                Article.ingested_at >= cutoff,
                Article.is_ai_related.is_(True),
                Article.is_duplicate.is_(False),
            )
            .order_by(Article.ingested_at.desc())
        )

        return list(session.execute(stmt).scalars().all())

    def has_new_articles_since(self, session: Session, since: datetime) -> bool:
        """Check if there are articles ingested after a given time."""
        stmt = select(func.count(Article.id)).where(Article.ingested_at > since)
        count = session.execute(stmt).scalar()
        return count > 0

    def _create_fallback_summary(
        self, session: Session, target_date: date, articles: list[Article], error_message: str
    ) -> DailySummary:
        """Create a fallback summary when LLM generation fails."""
        summary = DailySummary(
            date=datetime.combine(target_date, datetime.min.time(), tzinfo=UTC),
            summary_text=f"Summary generation failed: {error_message}",
            key_facts=[],
            article_ids=[a.id for a in articles],
        )
        session.add(summary)
        session.commit()
        return summary

    async def generate(
        self, session: Session, target_date: date | None = None, force: bool = False
    ) -> DailySummary:
        """Generate summary for recent articles.

        Args:
            session: Database session.
            target_date: Date to label the summary. Defaults to today.
            force: If True, regenerate even if cached.

        Returns:
            DailySummary model instance.
        """
        if target_date is None:
            target_date = datetime.now(UTC).date()

        # Check cache (unless forced)
        cached = self.get_cached_summary(session, target_date)
        if cached and not force:
            # Check if there are newer articles since the summary was created
            if not self.has_new_articles_since(session, cached.created_at):
                return cached
            # Delete stale cache
            session.delete(cached)
            session.commit()

        # Get recent articles (last 24 hours)
        articles = self.get_recent_articles(session, hours=24)

        if not articles:
            summary = DailySummary(
                date=datetime.combine(target_date, datetime.min.time(), tzinfo=UTC),
                summary_text="No articles for today.",
                key_facts=[],
                article_ids=[],
            )
            session.add(summary)
            session.commit()
            return summary

        # Prepare content with null coalescing for article fields
        articles_text = "\n\n".join(
            f"Title: {a.title or 'Untitled'}\nTopic: {a.topic or 'Unknown'}\nContent: {(a.content or '')[:500]}"
            for a in articles[:50]  # Limit to avoid token limits
        )

        # Generate summary with error handling
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=f"Articles for {target_date}:\n\n{articles_text}",
                config=GenerateContentConfig(
                    system_instruction=self.SYSTEM_PROMPT,
                    response_mime_type="application/json",
                ),
            )
        except Exception as e:
            logger.error("Google API error during summary generation: %s", e)
            return self._create_fallback_summary(
                session, target_date, articles, "LLM API error occurred."
            )

        # Validate response
        if not response.text:
            logger.error("LLM response has no text")
            return self._create_fallback_summary(
                session, target_date, articles, "LLM returned empty response."
            )

        # Parse JSON with error handling
        try:
            result = json.loads(response.text)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response as JSON: %s", e)
            return self._create_fallback_summary(
                session, target_date, articles, "Failed to parse LLM response."
            )

        # Create and save summary
        summary = DailySummary(
            date=datetime.combine(target_date, datetime.min.time(), tzinfo=UTC),
            summary_text=result.get("summary", ""),
            key_facts=result.get("key_facts", []),
            article_ids=[a.id for a in articles],
        )
        session.add(summary)
        session.commit()

        return summary
