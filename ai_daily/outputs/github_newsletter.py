"""GitHub trending repos newsletter generation and sending."""

import base64
import logging
from datetime import date, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_daily.config import config
from ai_daily.db import Article, Source

logger = logging.getLogger(__name__)


class GitHubNewsletterOutput:
    """Generate and send GitHub trending repos newsletter."""

    def __init__(self, gmail_service=None):
        self.gmail_service = gmail_service
        self.template_path = config.templates_dir / "github_hot_repos_email_template.html"

    def _load_template(self) -> str:
        """Load email template."""
        if self.template_path.exists():
            return self.template_path.read_text()
        # Fallback minimal template
        return """
        <html>
        <body style="background-color: #0d1117; color: #c9d1d9; font-family: sans-serif; padding: 20px;">
            <h1 style="color: #58a6ff;">🔥 GitHub Hot Repos - {{date}}</h1>
            {{repos}}
        </body>
        </html>
        """

    def get_github_articles(self, session: Session, hours: int = 24) -> List[Article]:
        """Get GitHub articles from the last N hours."""
        from datetime import timedelta

        # Get GitHub source IDs
        github_sources = session.execute(
            select(Source.id).where(Source.type == "github")
        ).scalars().all()

        if not github_sources:
            return []

        cutoff = datetime.utcnow() - timedelta(hours=hours)

        stmt = select(Article).where(
            Article.source_id.in_(github_sources),
            Article.ingested_at >= cutoff
        ).order_by(Article.ingested_at.desc())

        return list(session.execute(stmt).scalars().all())

    def _generate_repos_html(self, articles: List[Article]) -> str:
        """Generate HTML for repos."""
        if not articles:
            return "<p>No trending repos today.</p>"

        html = ""
        for article in articles[:15]:  # Limit to top 15
            title = escape(article.title or "Unknown Repo")
            url = escape(article.url or "#")
            content = article.content or ""

            # Parse metadata from content
            lines = content.split("\n")
            description = lines[0] if lines else ""
            language = "Unknown"
            stars = ""
            forks = ""

            for line in lines:
                if line.startswith("Language:"):
                    language = line.replace("Language:", "").strip()
                elif line.startswith("Stars:"):
                    stars = line.replace("Stars:", "").strip()
                elif line.startswith("Forks:"):
                    forks = line.replace("Forks:", "").strip()

            html += f"""
            <div class="repo-card">
                <p class="repo-name">
                    <a href="{url}">{title}</a>
                </p>
                <p class="repo-desc">{escape(description[:250])}</p>
                <div class="repo-meta">
                    <span>📝 {escape(language)}</span>
                    <span>⭐ {escape(stars)}</span>
                    {f'<span>🍴 {escape(forks)}</span>' if forks else ''}
                </div>
            </div>
            """

        return html

    def generate_html(self, articles: List[Article]) -> str:
        """Generate HTML email content."""
        template = self._load_template()

        html = template.replace("{{date}}", datetime.now().strftime("%B %d, %Y"))
        html = html.replace("{{year}}", str(datetime.now().year))

        repos_html = self._generate_repos_html(articles)
        html = html.replace("{{repos}}", repos_html)

        return html

    async def send(
        self,
        session: Session,
        recipients: Optional[List[str]] = None
    ) -> bool:
        """Generate and send GitHub newsletter.

        Args:
            session: Database session.
            recipients: List of email addresses. Defaults to config.

        Returns:
            True if sent successfully.
        """
        if not self.gmail_service:
            raise ValueError("Gmail service not initialized")

        if recipients is None:
            recipients = config.recipients

        if not recipients:
            raise ValueError("No recipients configured")

        # Get GitHub articles
        articles = self.get_github_articles(session, hours=24)

        if not articles:
            logger.info("No GitHub repos to send")
            return True

        # Generate HTML
        html_content = self.generate_html(articles)

        # Send to each recipient
        subject = f"🔥 GitHub Hot Repos - {datetime.now().strftime('%B %d, %Y')}"

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
                logger.info(f"GitHub newsletter sent to {recipient}")
            except Exception as e:
                failure_count += 1
                logger.error(f"Failed to send GitHub newsletter to {recipient}: {e}")
                continue

        logger.info(f"GitHub newsletter: {success_count} succeeded, {failure_count} failed")
        return success_count > 0
