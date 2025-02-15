import hashlib
import json
from dataclasses import dataclass
from typing import List, Optional, Dict
from pathlib import Path
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from openai import AsyncOpenAI
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from .utils import logger, error_handler, save_individual_email


@dataclass
class Article:
    title: str
    content: str
    source: str
    url: Optional[str]
    date: datetime
    topic: str
    hash: str = ""

    def __post_init__(self):
        # Generate content hash to help identify similar articles
        self.hash = hashlib.md5(
            f"{self.title}{self.content[:200]}".encode()
        ).hexdigest()


@dataclass
class NewsletterContent:
    summary: str
    key_facts: List[str]
    articles: List[Article]
    date: datetime


class NewsletterProcessor:
    def __init__(self):
        self.openai_client = AsyncOpenAI()

    def load_articles_from_files(
        self, from_date: datetime, to_date: datetime
    ) -> List[Article]:
        processed_dir = Path("data/emails/processed")
        files = [
            f
            for f in processed_dir.glob("*.json")
            if from_date <= datetime.strptime(f.name.split("_")[0], "%Y%m%d") <= to_date
        ]
        articles = []

        logger.info(f"Loading articles from {len(files)} processed email files")

        for file in files:
            try:
                data = json.load(file.open(encoding="utf-8"))
                articles.extend(
                    Article(
                        title=a["title"],
                        content=a["content"],
                        source=data["sender"],
                        url=a.get("url"),
                        date=datetime.strptime(file.name.split("_")[0], "%Y%m%d"),
                        topic=a["topic"],
                    )
                    for a in data.get("extracted_articles", [])
                )
            except Exception as e:
                logger.error(f"Error loading articles from {file.name}: {e}")

        return articles

    def _parse_email_date(self, date_str: str) -> datetime:
        """Parse email date string handling various formats including UTC with timezone offset"""
        try:
            # Remove the (UTC) suffix if present while keeping the timezone offset
            date_str = date_str.replace(" (UTC)", "")
            # Now parse with timezone offset
            return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
        except ValueError as e:
            try:
                # Try without timezone if that fails
                return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S")
            except ValueError:
                # Fallback to current date if parsing fails
                logger.warning(
                    f"Could not parse date: {date_str}. Error: {str(e)}. Using current datetime."
                )
                return datetime.now()

    @error_handler
    async def process_emails(self, emails: List[Dict]) -> List[Article]:
        """Process emails into structured articles"""
        articles = []

        for email in emails:
            try:
                # Extract articles from email using OpenAI
                extracted_data = await self._extract_articles_from_email(email)

                # Convert to Article objects
                for article_data in extracted_data.get("articles", []):
                    article = Article(
                        title=article_data["title"],
                        content=article_data["content"],
                        source=email["sender"],
                        url=article_data.get("url"),
                        date=self._parse_email_date(email["date"]),
                        topic=article_data["topic"],
                    )
                    articles.append(article)

                # Save processed email to processed directory
                email_copy = email.copy()
                email_copy["extracted_articles"] = extracted_data.get("articles", [])
                save_individual_email(email_copy, processed=True)

            except Exception as e:
                logger.error(f"Error processing email: {str(e)}")
                continue

        return articles

    async def _extract_articles_from_email(self, email: Dict) -> Dict:
        """Extract structured articles from email content, filtering by specific topics"""
        # Define the system prompt with clear instructions and topic filtering
        system_prompt = """
            You are an expert at extracting structured data from newsletter emails. Your task is to extract articles from the email content that match the following topics:
            - AI Research and Advances
            - AI Products, Tools, and Repositories
            - Data Science Techniques and Tips
            - Industry News and Trends

            For each matching article, identify:
            - Title
            - Main content
            - Topic category (must be one of the above topics)
            - Any URLs mentioned

            Output your response strictly in valid JSON with the following structure:
            {
                "articles": [
                    {
                        "title": "Article title",
                        "content": "Main content",
                        "topic": "Topic category",
                        "url": "URL if present (empty string if not)"
                    }
                ]
            }
            Do not include any additional text or explanation outside of this JSON structure.
            """

        # Prepare the user prompt with the email body
        prompt = f"""
            Email content:
            {email['body']}
            """

        try:
            completion = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )
            return json.loads(completion.choices[0].message.content)
        except Exception as e:
            logger.error(f"Error extracting articles: {str(e)}")
            return {"articles": []}

    def group_similar_articles(self, articles: List[Article]) -> List[List[Article]]:
        """Group similar articles together based on content similarity"""
        from difflib import SequenceMatcher

        def similarity_score(a: Article, b: Article) -> float:
            # Calculate similarity based on title and content
            title_sim = SequenceMatcher(None, a.title, b.title).ratio()
            content_sim = SequenceMatcher(
                None, a.content[:200], b.content[:200]
            ).ratio()
            return (title_sim * 0.6) + (content_sim * 0.4)

        groups = []
        used_articles = set()

        for article in articles:
            if article.hash in used_articles:
                continue

            group = [article]
            used_articles.add(article.hash)

            for other in articles:
                if other.hash in used_articles:
                    continue

                if similarity_score(article, other) > 0.6:  # Threshold for similarity
                    group.append(other)
                    used_articles.add(other.hash)

            groups.append(group)

        return groups

    async def generate_daily_summary(
        self, articles: List[Article]
    ) -> NewsletterContent:
        """Generate daily summary and key facts from articles"""
        # Filter for last day's articles
        yesterday = datetime.now(timezone.utc) - timedelta(days=2)
        recent_articles = [
            a for a in articles if a.date.replace(tzinfo=timezone.utc) > yesterday
        ]

        logger.info(f"Found {len(recent_articles)} articles for summary generation")

        if not recent_articles:
            return NewsletterContent(
                summary="No new articles for today.",
                key_facts=[],
                articles=[],
                date=datetime.now(),
            )

        # Prepare content for summary generation
        articles_text = "\n\n".join(
            f"Title: {a.title}\nContent: {a.content}" for a in recent_articles
        )

        # Refined prompt
        prompt = f"""
                    Articles:
                    {articles_text}
                    """

        system_prompt = """
            You are an expert in AI news and summarization. Below are daily newsletter articles categorized as follows:
            - AI Research and Advances
            - AI Products, Tools, and Repositories
            - Data Science Techniques and Tips
            - Industry News and Trends

            Your tasks are:
            1. Generate a complete summary that captures the key developments and trends across these categories.
            2. List the most important facts and developments as bullet points.

            Output your response in valid JSON with the following structure:
            {
                "summary": "A high-level summary of the day's AI news.",
                "key_facts": [
                    "Key fact 1",
                    "Key fact 2",
                    ...
                ]
            }

            Do not include any additional text or explanation outside of this JSON structure.
            """

        try:
            completion = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
            )

            result = json.loads(completion.choices[0].message.content)

            return NewsletterContent(
                summary=result["summary"],
                key_facts=result["key_facts"],
                articles=recent_articles,
                date=datetime.now(),
            )

        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return None
