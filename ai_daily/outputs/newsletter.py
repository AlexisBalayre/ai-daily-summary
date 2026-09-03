"""Newsletter email generation and sending."""

import base64
import json
import logging
from datetime import UTC, date, datetime, timedelta
from email.mime.audio import MIMEAudio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_daily.config import config
from ai_daily.db import Article, DailySummary, Source
from ai_daily.outputs.summary_generator import SummaryGenerator

logger = logging.getLogger(__name__)

# Mirror of EnrichmentProcessor.MODEL_RELEASE_TAG (kept local to avoid importing
# the enrichment module, which pulls in the LLM/embedding clients).
MODEL_RELEASE_TAG = "model-release"


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
        </body>
        </html>
        """

    def get_newsletter_articles(self, session: Session, hours: int = 24) -> list[Article]:
        """Get non-GitHub articles from the last N hours."""
        # Get GitHub source IDs to exclude
        github_sources = (
            session.execute(select(Source.id).where(Source.type == "github")).scalars().all()
        )
        github_source_ids = set(github_sources)

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

        all_articles = list(session.execute(stmt).scalars().all())

        # Filter out GitHub articles
        return [a for a in all_articles if a.source_id not in github_source_ids]

    def get_release_radar_articles(self, session: Session, hours: int = 24) -> list[Article]:
        """Get model-release articles from the last N hours (default: 24h).

        The newsletter shows only the freshest releases — the full history lives
        on the dashboard's Releases page and arrives as instant alerts.
        """
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        stmt = (
            select(Article)
            .where(
                Article.ingested_at >= cutoff,
                Article.is_duplicate.is_(False),
                Article.tags.any(MODEL_RELEASE_TAG),
            )
            .order_by(Article.ingested_at.desc())
        )
        return list(session.execute(stmt).scalars().all())

    TOP_STORIES_COUNT = 10

    TOP_SELECTION_PROMPT = """You curate a daily AI newsletter for a busy reader who only wants
the essential news. From the numbered list of today's articles, select the {n} most important:
major model releases, significant research results, and big industry moves. Prefer primary
announcements over commentary or tutorials, and skip near-duplicate stories.

{listing}

Respond ONLY with valid JSON: {{"selected": [numbers of the chosen articles]}}"""

    async def _select_top_articles(self, articles: list[Article]) -> list[Article]:
        """LLM curation: keep only the day's most essential stories.

        Falls back to the most recent TOP_STORIES_COUNT articles when the
        selection call fails — the newsletter must always go out.
        """
        n = self.TOP_STORIES_COUNT
        if len(articles) <= n:
            return articles

        listing = "\n".join(
            f"{i}. {a.title or 'Untitled'} — {(a.summary or a.content or '')[:150]}"
            for i, a in enumerate(articles)
        )
        try:
            from google.genai.types import GenerateContentConfig

            response = await self.summary_generator.client.aio.models.generate_content(
                model=self.summary_generator.model,
                contents=self.TOP_SELECTION_PROMPT.format(n=n, listing=listing),
                config=GenerateContentConfig(response_mime_type="application/json"),
            )
            indices = json.loads(response.text).get("selected", [])
            picked = [articles[i] for i in indices if isinstance(i, int) and 0 <= i < len(articles)]
            if picked:
                return picked[:n]
        except Exception as e:
            logger.warning(f"Top-story selection failed, falling back to recency: {e}")
        return articles[:n]

    def _categorize_articles(self, articles: list[Article]) -> dict:
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

            if any(
                word in topic_lower for word in ["research", "study", "advance", "breakthrough"]
            ):
                categories["AI Research and Advances"].append(article)
            elif any(
                word in topic_lower for word in ["tool", "product", "repository", "framework"]
            ):
                categories["AI Products, Tools, and Repositories"].append(article)
            elif any(word in topic_lower for word in ["tip", "technique", "guide", "tutorial"]):
                categories["Data Science Techniques and Tips"].append(article)
            else:
                categories["Industry News and Trends"].append(article)

        return categories

    RADAR_MAX_ITEMS = 5

    def _render_release_radar(self, articles: list[Article]) -> str:
        """Compact one-line-per-release block, or '' when there are none."""
        if not articles:
            return ""
        items = ""
        for a in articles[: self.RADAR_MAX_ITEMS]:
            title = escape(a.title or "Untitled")
            url = escape(a.url or "#")
            source = escape(a.source.name if a.source else "")
            items += f'''
                    <div class="radar-item">
                      <p class="radar-title"><a href="{url}">{title}</a>
                        <span class="radar-source">&nbsp;— {source}</span></p>
                    </div>'''
        return f"""
                    <div class="radar">
                      <p class="radar-label">🚀 Released in the last 24h</p>
                      {items}
                    </div>"""

    def generate_html(
        self,
        summary: DailySummary,
        articles: list[Article],
        release_articles: list[Article] | None = None,
    ) -> str:
        """Generate HTML email content."""
        template = self._load_template()

        # Replace placeholders
        html = template.replace("{{date}}", datetime.now(UTC).strftime("%B %d, %Y"))
        html = html.replace("{{year}}", str(datetime.now(UTC).year))
        html = html.replace("{{brand}}", escape(config.brand))
        html = html.replace("{{release_radar}}", self._render_release_radar(release_articles or []))

        # Key facts - handle both list and other types
        key_facts_html = ""
        if summary.key_facts:
            facts = (
                summary.key_facts if isinstance(summary.key_facts, list) else [summary.key_facts]
            )
            for fact in facts[:6]:
                key_facts_html += f"<li>{escape(str(fact))}</li>"
        html = html.replace("{{key_facts}}", key_facts_html)

        # Articles by category
        categories = self._categorize_articles(articles)
        articles_html = ""

        for category, cat_articles in categories.items():
            if cat_articles:
                articles_html += f"""
                <div class="category" style="margin-bottom: 28px;">
                    <h3 class="category-title" style="font-family: 'Inter', -apple-system, sans-serif; font-size: 14px; font-weight: 600; color: #18181b; margin: 0 0 16px; padding-left: 12px; border-left: 3px solid #18181b;">{escape(category)}</h3>
                """
                for article in cat_articles:
                    title = escape(article.title or "Untitled")
                    url = escape(article.url or "#")
                    excerpt = article.summary or (article.content or "")
                    truncated_content = (
                        escape(excerpt[:280]) + "..." if len(excerpt) > 280 else escape(excerpt)
                    )
                    articles_html += f'''
                    <div class="article-card" style="background: #fafafa; border: 1px solid #e4e4e7; border-radius: 6px; padding: 20px; margin-bottom: 12px;">
                        <h4 class="article-title" style="font-family: 'Inter', -apple-system, sans-serif; font-size: 15px; font-weight: 600; color: #18181b; margin: 0 0 8px; line-height: 1.4;">
                            <a href="{url}" style="color: inherit; text-decoration: none;">{title}</a>
                        </h4>
                        <p class="article-excerpt" style="font-family: 'Source Serif 4', Georgia, serif; font-size: 15px; line-height: 1.6; color: #52525b; margin: 0 0 12px;">{truncated_content}</p>
                        <a href="{url}" class="read-more" style="font-family: 'Inter', -apple-system, sans-serif; font-size: 13px; font-weight: 500; color: #3b82f6; text-decoration: none;">Read more</a>
                    </div>
                    '''
                articles_html += "</div>"

        html = html.replace("{{articles}}", articles_html)

        # Remove GitHub placeholder if present
        html = html.replace("{{github_repos}}", "")

        return html

    def _build_plaintext(
        self, articles: list[Article], release_articles: list[Article] | None = None
    ) -> str:
        """Plain-text alternative: article titles, links, and excerpts by section."""
        lines = ["AI Daily Briefing", ""]
        if release_articles:
            lines.append("RELEASED IN THE LAST 24H")
            for a in release_articles[: self.RADAR_MAX_ITEMS]:
                lines.append(f"- {a.title or 'Untitled'}")
                if a.url:
                    lines.append(f"  {a.url}")
            lines.append("")
        for category, cat_articles in self._categorize_articles(articles).items():
            if not cat_articles:
                continue
            lines.append(category.upper())
            for article in cat_articles:
                lines.append(f"- {article.title or 'Untitled'}")
                if article.url:
                    lines.append(f"  {article.url}")
            lines.append("")
        return "\n".join(lines).strip() + "\n"

    def _build_message(
        self,
        subject: str,
        recipient: str,
        html_content: str,
        text_content: str,
        audio_path: Path | None,
    ) -> MIMEMultipart:
        """Assemble the email: text+html alternative, plus the audio attachment
        as a `mixed` wrapper when a briefing was generated."""
        alternative = MIMEMultipart("alternative")
        alternative.attach(MIMEText(text_content, "plain"))
        alternative.attach(MIMEText(html_content, "html"))

        if audio_path and Path(audio_path).exists():
            message = MIMEMultipart("mixed")
            message.attach(alternative)
            audio = MIMEAudio(Path(audio_path).read_bytes(), _subtype="wav")
            audio.add_header("Content-Disposition", "attachment", filename=Path(audio_path).name)
            message.attach(audio)
        else:
            message = alternative

        message["Subject"] = subject
        message["To"] = recipient
        message["From"] = "me"
        return message

    async def send(
        self,
        session: Session,
        target_date: date | None = None,
        recipients: list[str] | None = None,
        audio_path: Path | None = None,
    ) -> bool:
        """Generate and send newsletter.

        Args:
            session: Database session.
            target_date: Date to send newsletter for.
            recipients: List of email addresses. Defaults to config.
            audio_path: Optional spoken-briefing WAV to attach to the email.

        Returns:
            True if sent successfully.
        """
        if not self.gmail_service:
            raise ValueError("Gmail service not initialized")

        if target_date is None:
            target_date = datetime.now(UTC).date()

        if recipients is None:
            recipients = config.get_newsletter_recipients()

        if not recipients:
            raise ValueError("No recipients configured")

        # Generate summary
        summary = await self.summary_generator.generate(session, target_date)

        # Essentials only: curate the day's top stories + last-24h releases
        articles = await self._select_top_articles(self.get_newsletter_articles(session, hours=24))
        release_articles = self.get_release_radar_articles(session)

        # Generate HTML + plain-text alternative
        html_content = self.generate_html(summary, articles, release_articles)
        text_content = self._build_plaintext(articles, release_articles)

        # Send to each recipient
        subject = f"AI-Daily Newsletter - {target_date.strftime('%B %d, %Y')}"

        success_count = 0
        failure_count = 0

        for recipient in recipients:
            message = self._build_message(
                subject, recipient, html_content, text_content, audio_path
            )

            raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
            try:
                self.gmail_service.users().messages().send(userId="me", body={"raw": raw}).execute()
                success_count += 1
                logger.info(f"Newsletter sent successfully to {recipient}")
            except Exception as e:
                failure_count += 1
                logger.error(f"Failed to send newsletter to {recipient}: {e}")
                continue

        logger.info(f"Newsletter send complete: {success_count} succeeded, {failure_count} failed")
        return success_count > 0

    def send_release_alert(
        self, articles: list[Article], recipients: list[str] | None = None
    ) -> bool:
        """Send an immediate alert email for freshly detected model releases.

        Used by the ETL job the moment new `model-release` articles are enriched,
        so important releases don't wait for the daily newsletter.
        """
        if not self.gmail_service:
            raise ValueError("Gmail service not initialized")
        if not articles:
            return False
        if recipients is None:
            recipients = config.get_newsletter_recipients()
        if not recipients:
            logger.warning("No recipients configured for release alert")
            return False

        if len(articles) == 1:
            subject = f"🚀 New AI model release: {articles[0].title or 'Untitled'}"
        else:
            subject = f"🚀 {len(articles)} new AI model releases"

        cards = ""
        text_lines = ["New AI model releases:", ""]
        for a in articles:
            title = escape(a.title or "Untitled")
            url = escape(a.url or "#")
            source = escape(a.source.name if a.source else "")
            desc = escape(a.summary or "")
            cards += (
                f'<div style="margin:0 0 20px;padding:16px 18px;border:1px solid #cfe0f5;'
                f'border-radius:8px;background:#f0f7ff;font-family:Inter,-apple-system,sans-serif;">'
                f'<div style="font-size:16px;font-weight:600;margin:0 0 4px;">'
                f'<a href="{url}" style="color:#18181b;text-decoration:none;">{title}</a></div>'
                f'<div style="font-size:12px;color:#1d4ed8;font-weight:500;">{source}</div>'
                f'<p style="font-size:14px;color:#3f3f46;line-height:1.55;margin:8px 0 0;">{desc}</p>'
                f"</div>"
            )
            text_lines.append(f"- {a.title or 'Untitled'}")
            if a.url:
                text_lines.append(f"  {a.url}")
        html = (
            f'<div style="max-width:600px;margin:0 auto;padding:24px;">'
            f'<h2 style="font-family:Inter,-apple-system,sans-serif;font-size:18px;">🚀 New model release</h2>{cards}</div>'
        )
        text = "\n".join(text_lines)

        sent = 0
        for recipient in recipients:
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["To"] = recipient
            message["From"] = "me"
            message.attach(MIMEText(text, "plain"))
            message.attach(MIMEText(html, "html"))
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
            try:
                self.gmail_service.users().messages().send(userId="me", body={"raw": raw}).execute()
                sent += 1
            except Exception as e:
                logger.error(f"Failed to send release alert to {recipient}: {e}")
        logger.info(
            f"Release alert sent to {sent}/{len(recipients)} recipients for {len(articles)} release(s)"
        )
        return sent > 0
