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
        """Generate HTML for repos with modern light theme styling."""
        if not articles:
            return '''<p style="font-family: 'DM Sans', sans-serif; font-size: 14px; color: #6e7781; text-align: center; padding: 40px;">No trending repos detected today.</p>'''

        html = ""
        for idx, article in enumerate(articles[:15], 1):  # Limit to top 15
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

            # Truncate description
            desc_text = escape(description[:200]) + "..." if len(description) > 200 else escape(description)

            html += f'''
            <div class="repo-card" style="background: #f6f8fa; border: 1px solid #d1d9e0; border-radius: 12px; padding: 24px; margin: 16px 0; position: relative;">
                <span class="repo-rank" style="position: absolute; top: -10px; right: 20px; font-family: 'Outfit', sans-serif; font-size: 11px; font-weight: 700; color: #8250df; background: #fbefff; padding: 4px 12px; border-radius: 20px; border: 1px solid rgba(130, 80, 223, 0.2); letter-spacing: 1px;">#{idx:02d}</span>
                <p class="repo-name" style="font-family: 'Outfit', sans-serif; font-size: 18px; font-weight: 600; margin: 0 0 12px 0; line-height: 1.3;">
                    <a href="{url}" style="color: #0969da; text-decoration: none;">{title}</a>
                </p>
                <p class="repo-desc" style="font-family: 'DM Sans', sans-serif; font-size: 14px; color: #424a53; line-height: 1.65; margin: 0 0 18px 0; padding-left: 14px; border-left: 3px solid #d1d9e0;">{desc_text}</p>
                <div class="repo-meta" style="display: flex; flex-wrap: wrap; gap: 10px; font-family: 'Fira Code', monospace; font-size: 12px;">
                    <span class="meta-tag meta-lang" style="display: inline-flex; align-items: center; gap: 6px; color: #0969da; background: #ddf4ff; padding: 6px 12px; border-radius: 6px; border: 1px solid rgba(9, 105, 218, 0.15); font-weight: 500;">&#128221; {escape(language)}</span>
                    <span class="meta-tag meta-stars" style="display: inline-flex; align-items: center; gap: 6px; color: #bf5700; background: #fff8f2; padding: 6px 12px; border-radius: 6px; border: 1px solid rgba(191, 87, 0, 0.15); font-weight: 500;">&#11088; {escape(stars)}</span>
                    {f'<span class="meta-tag meta-forks" style="display: inline-flex; align-items: center; gap: 6px; color: #1a7f37; background: #dafbe1; padding: 6px 12px; border-radius: 6px; border: 1px solid rgba(26, 127, 55, 0.15); font-weight: 500;">&#127860; {escape(forks)}</span>' if forks else ''}
                </div>
            </div>
            '''

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
