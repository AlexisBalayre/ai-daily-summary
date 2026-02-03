"""Generate daily summaries from articles."""

import json
from datetime import date, datetime, timedelta
from typing import List, Optional

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_daily.config import config
from ai_daily.db import Article, DailySummary


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
        if config.llm.provider == "ollama":
            self.client = AsyncOpenAI(
                base_url=config.llm.ollama_base_url,
                api_key="ollama"
            )
        else:
            self.client = AsyncOpenAI()
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

        # Prepare content
        articles_text = "\n\n".join(
            f"Title: {a.title}\nTopic: {a.topic}\nContent: {a.content[:500]}"
            for a in articles[:50]  # Limit to avoid token limits
        )

        # Generate summary
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": f"Articles for {target_date}:\n\n{articles_text}"}
            ],
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)

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
