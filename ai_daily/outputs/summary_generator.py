"""Generate daily summaries from articles."""

import json
import logging
from datetime import date, datetime, timedelta
from typing import List, Optional

from google import genai
from google.genai.types import GenerateContentConfig
from sqlalchemy import select
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

    def get_cached_summary(self, session: Session, target_date: date) -> Optional[DailySummary]:
        """Get cached summary for date if exists."""
        stmt = select(DailySummary).where(
            DailySummary.date == datetime.combine(target_date, datetime.min.time())
        )
        return session.execute(stmt).scalar_one_or_none()

    def get_articles_for_date(self, session: Session, target_date: date) -> List[Article]:
        """Get articles for a specific date."""
        start = datetime.combine(target_date, datetime.min.time())
        end = start + timedelta(days=1)

        stmt = select(Article).where(
            Article.ingested_at >= start,
            Article.ingested_at < end
        ).order_by(Article.ingested_at.desc())

        return list(session.execute(stmt).scalars().all())

    def _create_fallback_summary(
        self, session: Session, target_date: date, articles: List[Article], error_message: str
    ) -> DailySummary:
        """Create a fallback summary when LLM generation fails."""
        summary = DailySummary(
            date=datetime.combine(target_date, datetime.min.time()),
            summary_text=f"Summary generation failed: {error_message}",
            key_facts=[],
            article_ids=[a.id for a in articles],
        )
        session.add(summary)
        session.commit()
        return summary

    async def generate(self, session: Session, target_date: Optional[date] = None) -> DailySummary:
        """Generate summary for a date.

        Args:
            session: Database session.
            target_date: Date to summarize. Defaults to today.

        Returns:
            DailySummary model instance.
        """
        if target_date is None:
            target_date = date.today()

        # Check cache
        cached = self.get_cached_summary(session, target_date)
        if cached:
            return cached

        # Get articles
        articles = self.get_articles_for_date(session, target_date)

        if not articles:
            summary = DailySummary(
                date=datetime.combine(target_date, datetime.min.time()),
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
            return self._create_fallback_summary(session, target_date, articles, "LLM API error occurred.")

        # Validate response
        if not response.text:
            logger.error("LLM response has no text")
            return self._create_fallback_summary(session, target_date, articles, "LLM returned empty response.")

        # Parse JSON with error handling
        try:
            result = json.loads(response.text)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response as JSON: %s", e)
            return self._create_fallback_summary(session, target_date, articles, "Failed to parse LLM response.")

        # Create and save summary
        summary = DailySummary(
            date=datetime.combine(target_date, datetime.min.time()),
            summary_text=result.get("summary", ""),
            key_facts=result.get("key_facts", []),
            article_ids=[a.id for a in articles],
        )
        session.add(summary)
        session.commit()

        return summary
