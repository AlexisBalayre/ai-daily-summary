"""LLM-based content parser for extracting structured articles."""

import json
from typing import Dict, List

from openai import AsyncOpenAI

from ai_daily.config import config
from ai_daily.etl.types import RawContent


class LLMParser:
    """Parse raw content into structured articles using LLM."""

    SYSTEM_PROMPT = """You are an expert at extracting structured data from newsletter content.

Extract articles that match these topics:
- AI Research and Advances
- AI Products, Tools, and Repositories
- Data Science Techniques and Tips
- Industry News and Trends

For each article, identify:
- title: Clear, descriptive title
- content: Main content summary (2-3 sentences)
- topic: One of the categories above
- url: URL if mentioned

Output valid JSON:
{
    "articles": [
        {"title": "...", "content": "...", "topic": "...", "url": "..."}
    ]
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

    async def parse(self, raw_content: RawContent) -> List[Dict]:
        """Parse raw content into structured articles.

        Args:
            raw_content: The raw content to parse.

        Returns:
            List of article dictionaries with title, content, topic, url.
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": f"Content:\n{raw_content.content[:8000]}"}
                ],
                response_format={"type": "json_object"},
            )

            result = json.loads(response.choices[0].message.content)
            articles = result.get("articles", [])

            for article in articles:
                article["source_name"] = raw_content.source_name
                article["external_id"] = raw_content.external_id
                if not article.get("url"):
                    article["url"] = raw_content.url

            return articles
        except Exception:
            return [{
                "title": raw_content.title,
                "content": raw_content.content[:1000],
                "topic": "Industry News and Trends",
                "url": raw_content.url,
                "source_name": raw_content.source_name,
                "external_id": raw_content.external_id,
            }]
