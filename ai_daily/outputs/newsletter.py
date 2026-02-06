"""Newsletter email generation and sending."""

import base64
import logging
from datetime import date, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from pathlib import Path
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from ai_daily.config import config
from ai_daily.db import Article, DailySummary, Source
from ai_daily.outputs.summary_generator import SummaryGenerator

logger = logging.getLogger(__name__)


class NewsletterOutput:
    """Generate and send newsletter emails."""

    def __init__(self, gmail_service=None):
        self.gmail_service = gmail_service
        self.summary_generator = SummaryGenerator()
        self.template_path = config.templates_dir / "ai_daily_news_email_template.html"

    def _load_template(self) -> str:
        """Load email template."""
        if self.template_path.exists():
            return self.template_path.read_text()
        # Fallback minimal template
        return """
        <html>
        <body>
            <h1>AI Daily Newsletter - {{date}}</h1>
            <h2>Summary</h2>
            <p>{{summary}}</p>
            <h2>Key Facts</h2>
            <ul>{{key_facts}}</ul>
            <h2>Articles</h2>
            {{articles}}
            {{github_repos}}
        </body>
        </html>
        """

    def _separate_github_articles(self, articles: List[Article], session: Session) -> Tuple[List[Article], List[Article]]:
        """Separate GitHub repos from regular articles."""
        # Get GitHub source IDs
        github_sources = session.query(Source.id).filter(Source.type == "github").all()
        github_source_ids = {s.id for s in github_sources}

        regular = []
        github = []

        for article in articles:
            if article.source_id in github_source_ids:
                github.append(article)
            else:
                regular.append(article)

        return regular, github

    def _categorize_articles(self, articles: List[Article]) -> dict:
        """Categorize articles by topic."""
        categories = {
            "AI Research and Advances": [],
            "AI Products, Tools, and Repositories": [],
            "Data Science Techniques and Tips": [],
            "Industry News and Trends": [],
        }

        for article in articles:
            topic = article.topic or ""
            topic_lower = topic.lower()

            if any(word in topic_lower for word in ["research", "study", "advance", "breakthrough"]):
                categories["AI Research and Advances"].append(article)
            elif any(word in topic_lower for word in ["tool", "product", "repository", "framework"]):
                categories["AI Products, Tools, and Repositories"].append(article)
            elif any(word in topic_lower for word in ["tip", "technique", "guide", "tutorial"]):
                categories["Data Science Techniques and Tips"].append(article)
            else:
                categories["Industry News and Trends"].append(article)

        return categories

    def _generate_github_html(self, github_articles: List[Article]) -> str:
        """Generate HTML for GitHub repos section."""
        if not github_articles:
            return ""

        html = """
        <h2>🔥 Trending on GitHub</h2>
        <div style="margin: 15px 0;">
        """

        for article in github_articles[:10]:  # Limit to top 10
            title = escape(article.title or "Unknown Repo")
            url = escape(article.url or "#")
            content = article.content or ""

            # Parse metadata from content (format: "description\n\nLanguage: X\nStars: Y\nForks: Z")
            lines = content.split("\n")
            description = lines[0] if lines else ""
            language = "Unknown"
            stars = ""

            for line in lines:
                if line.startswith("Language:"):
                    language = line.replace("Language:", "").strip()
                elif line.startswith("Stars:"):
                    stars = line.replace("Stars:", "").strip()

            html += f"""
            <div style="border: 1px solid #dddddd; border-left: 4px solid #238636; padding: 12px; margin: 10px 0;">
                <h4 style="margin: 0 0 8px 0;">
                    <a href="{url}" style="color: #0066cc; text-decoration: none;">{title}</a>
                </h4>
                <p style="margin: 0 0 8px 0; color: #586069; font-size: 14px;">{escape(description[:200])}</p>
                <div style="font-size: 12px; color: #586069;">
                    <span style="margin-right: 15px;">📝 {escape(language)}</span>
                    <span>⭐ {escape(stars)}</span>
                </div>
            </div>
            """

        html += "</div>"
        return html

    def generate_html(self, summary: DailySummary, articles: List[Article], github_articles: List[Article]) -> str:
        """Generate HTML email content."""
        template = self._load_template()

        # Replace placeholders
        html = template.replace("{{date}}", datetime.now().strftime("%B %d, %Y"))
        html = html.replace("{{summary}}", escape(summary.summary_text or ""))
        html = html.replace("{{year}}", str(datetime.now().year))

        # Key facts - handle both list and other types
        key_facts_html = ""
        if summary.key_facts:
            facts = summary.key_facts if isinstance(summary.key_facts, list) else [summary.key_facts]
            for fact in facts:
                key_facts_html += f"<li>{escape(str(fact))}</li>"
        html = html.replace("{{key_facts}}", key_facts_html)

        # Articles by category (excluding GitHub)
        categories = self._categorize_articles(articles)
        articles_html = ""

        for category, cat_articles in categories.items():
            if cat_articles:
                articles_html += f"<h3>{escape(category)}</h3>"
                for article in cat_articles:
                    # Null coalescing for article fields
                    title = escape(article.title or "Untitled")
                    url = escape(article.url or "#")
                    content = article.content or ""
                    truncated_content = escape(content[:500]) + "..." if content else ""
                    articles_html += f"""
                    <h4>{title}</h4>
                    <p>{truncated_content}</p>
                    <p><a href="{url}">Read more</a></p>
                    """

        html = html.replace("{{articles}}", articles_html)

        # GitHub repos section
        github_html = self._generate_github_html(github_articles)
        html = html.replace("{{github_repos}}", github_html)

        return html

    async def send(
        self,
        session: Session,
        target_date: Optional[date] = None,
        recipients: Optional[List[str]] = None
    ) -> bool:
        """Generate and send newsletter.

        Args:
            session: Database session.
            target_date: Date to send newsletter for.
            recipients: List of email addresses. Defaults to config.

        Returns:
            True if sent successfully.
        """
        if not self.gmail_service:
            raise ValueError("Gmail service not initialized")

        if target_date is None:
            target_date = date.today()

        if recipients is None:
            recipients = config.recipients

        if not recipients:
            raise ValueError("No recipients configured")

        # Generate summary
        summary = await self.summary_generator.generate(session, target_date)

        # Get articles (last 24 hours)
        all_articles = self.summary_generator.get_recent_articles(session, hours=24)

        # Separate GitHub repos from regular articles
        articles, github_articles = self._separate_github_articles(all_articles, session)

        # Generate HTML
        html_content = self.generate_html(summary, articles, github_articles)

        # Send to each recipient
        subject = f"AI-Daily Newsletter - {target_date.strftime('%B %d, %Y')}"

        success_count = 0
        failure_count = 0

        for recipient in recipients:
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["To"] = recipient
            message["From"] = "me"

            part = MIMEText(html_content, "html")
            message.attach(part)

            raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
            try:
                self.gmail_service.users().messages().send(
                    userId="me",
                    body={"raw": raw}
                ).execute()
                success_count += 1
                logger.info(f"Newsletter sent successfully to {recipient}")
            except Exception as e:
                failure_count += 1
                logger.error(f"Failed to send newsletter to {recipient}: {e}")
                continue

        logger.info(f"Newsletter send complete: {success_count} succeeded, {failure_count} failed")
        return success_count > 0
