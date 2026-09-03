"""LLM-based content parser for extracting structured articles."""

import json
import logging

from google import genai
from google.genai.types import GenerateContentConfig

from ai_daily.config import config
from ai_daily.etl.types import RawContent

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = {"title", "content", "topic"}


class LLMParser:
    """Parse raw content into structured articles using LLM."""

    SYSTEM_PROMPT = """You are an expert at extracting structured data from newsletter content.

Extract articles that match these topics:
- AI Research and Advances
- AI Products, Tools, and Repositories
- Data Science Techniques and Tips
- Industry News and Trends

For each article, identify:
- title: Clear, descriptive title (required)
- content: Main content summary, 2-3 sentences (required)
- topic: One of the categories above (required)
- url: URL if mentioned

You MUST output valid JSON with this exact structure:
{
    "articles": [
        {"title": "...", "content": "...", "topic": "...", "url": "..."}
    ]
}"""

    MAX_RETRIES = 2

    def __init__(self):
        self.client = genai.Client(api_key=config.llm.google_api_key)
        self.model = config.llm.model

    def _validate_articles(self, articles: list[dict]) -> str | None:
        """Validate that all articles have required fields.

        Returns None if valid, or an error description if invalid.
        """
        if not isinstance(articles, list):
            return "Expected a list of articles"
        if not articles:
            return "No articles extracted"
        for i, article in enumerate(articles):
            missing = REQUIRED_FIELDS - set(article.keys())
            if missing:
                return f"Article {i} missing fields: {missing}"
            for field in REQUIRED_FIELDS:
                if not isinstance(article[field], str) or not article[field].strip():
                    return f"Article {i} has empty or non-string '{field}'"
        return None

    async def _call_llm(self, content: str) -> dict:
        """Make a single LLM call and parse the JSON response."""
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=f"Content:\n{content}",
            config=GenerateContentConfig(
                system_instruction=self.SYSTEM_PROMPT,
                response_mime_type="application/json",
            ),
        )
        return json.loads(response.text)

    async def parse(self, raw_content: RawContent) -> list[dict]:
        """Parse raw content into structured articles with retry on bad format."""
        try:
            content = raw_content.content[:8000]
            result = await self._call_llm(content)
            articles = result.get("articles", [])

            error = self._validate_articles(articles)
            for attempt in range(self.MAX_RETRIES):
                if error is None:
                    break
                logger.warning(
                    f"LLM output invalid ({error}), retry {attempt + 1}/{self.MAX_RETRIES}"
                )
                result = await self._call_llm(content)
                articles = result.get("articles", [])
                error = self._validate_articles(articles)

            if error is not None:
                logger.warning(f"LLM retries exhausted ({error}), using fallback")
                return self._fallback(raw_content)

            for article in articles:
                article["source_name"] = raw_content.source_name
                article["external_id"] = raw_content.external_id
                if not article.get("url"):
                    article["url"] = raw_content.url

            return articles
        except Exception as e:
            logger.warning(f"LLM parse failed ({e}), using fallback")
            return self._fallback(raw_content)

    def _fallback(self, raw_content: RawContent) -> list[dict]:
        """Return raw content as a single article when LLM fails."""
        return [
            {
                "title": raw_content.title,
                "content": raw_content.content[:1000],
                "topic": "Industry News and Trends",
                "url": raw_content.url,
                "source_name": raw_content.source_name,
                "external_id": raw_content.external_id,
            }
        ]
