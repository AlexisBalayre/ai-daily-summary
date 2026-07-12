"""Job definitions for orchestrator."""

import logging
from datetime import date, datetime, timezone
from typing import Any, Dict

from sqlalchemy import select

from ai_daily.db import Article, get_session, init_db
from ai_daily.db.seed import seed_sources
from ai_daily.etl import ETLPipeline
from ai_daily.etl.extractors.gmail import GmailExtractor
from ai_daily.orchestrator.types import JobContext
from ai_daily.outputs import GitHubNewsletterOutput, NewsletterOutput, TTSBriefingOutput
from ai_daily.outputs.newsletter import MODEL_RELEASE_TAG

logger = logging.getLogger(__name__)


def _alert_new_releases(since: datetime) -> int:
    """Email an instant alert for model-release articles ingested since `since`.

    Uses ingested_at (naive UTC, like the rest of the article queries) so it fires
    once per release — the run that ingests it — and never re-alerts old ones.
    """
    with get_session() as session:
        stmt = (
            select(Article)
            .where(
                Article.ingested_at >= since,
                Article.is_duplicate == False,
                Article.tags.any(MODEL_RELEASE_TAG),
            )
            .order_by(Article.ingested_at.desc())
        )
        releases = list(session.execute(stmt).scalars().all())
        if not releases:
            return 0
        gmail = GmailExtractor()
        NewsletterOutput(gmail_service=gmail.service).send_release_alert(releases)
        return len(releases)


async def run_etl(context: JobContext) -> Dict[str, Any]:
    """Run ETL pipeline for all sources."""
    logger.info(f"Starting ETL job (run_id={context.run_id})")

    # Ensure database is ready
    init_db()
    seed_sources()

    # Naive UTC, matching ingested_at's storage, so the release query below lines up.
    run_start = datetime.now(timezone.utc).replace(tzinfo=None)

    pipeline = ETLPipeline()
    metrics = await pipeline.run_all()

    logger.info(f"ETL complete: {metrics}")

    # Instant alert for any model releases detected in this run.
    try:
        alerted = _alert_new_releases(run_start)
        if isinstance(metrics, dict):
            metrics = {**metrics, "releases_alerted": alerted}
    except Exception as e:
        logger.warning(f"Release alert step failed (ETL still succeeded): {e}")

    return metrics


async def run_newsletter(context: JobContext) -> Dict[str, Any]:
    """Generate and send the newsletter with the spoken briefing attached."""
    logger.info(f"Starting newsletter job (run_id={context.run_id})")

    with get_session() as session:
        # Generate the audio briefing first, but best-effort: a TTS failure must
        # never block the newsletter itself. On failure we send without audio.
        audio_path = None
        try:
            tts = TTSBriefingOutput()
            audio_path, _ = await tts.generate(session, target_date=date.today())
        except Exception as e:
            logger.warning(f"Briefing audio unavailable, sending newsletter without it: {e}")

        gmail_extractor = GmailExtractor()
        newsletter = NewsletterOutput(gmail_service=gmail_extractor.service)

        success = await newsletter.send(
            session, target_date=date.today(), audio_path=audio_path
        )

        return {
            "sent": success,
            "audio_attached": audio_path is not None,
            "date": date.today().isoformat(),
        }


async def run_github_newsletter(context: JobContext) -> Dict[str, Any]:
    """Generate and send GitHub trending repos newsletter."""
    logger.info(f"Starting GitHub newsletter job (run_id={context.run_id})")

    with get_session() as session:
        gmail_extractor = GmailExtractor()
        github_newsletter = GitHubNewsletterOutput(gmail_service=gmail_extractor.service)

        success = await github_newsletter.send(session)

        return {
            "sent": success,
            "date": date.today().isoformat(),
        }


async def run_tts(context: JobContext) -> Dict[str, Any]:
    """Generate TTS audio briefing, sync to iCloud, and email."""
    logger.info(f"Starting TTS job (run_id={context.run_id})")

    with get_session() as session:
        tts = TTSBriefingOutput()
        audio_path, sync_path = await tts.generate(session, target_date=date.today())

        # Send audio by email
        email_sent = False
        try:
            gmail_extractor = GmailExtractor()
            email_sent = _send_audio_email(
                gmail_service=gmail_extractor.service,
                audio_path=audio_path,
                target_date=date.today(),
            )
        except Exception as e:
            logger.warning(f"Failed to email audio briefing: {e}")

        return {
            "audio_path": str(audio_path),
            "sync_path": str(sync_path) if sync_path else None,
            "email_sent": email_sent,
            "date": date.today().isoformat(),
        }


def _send_audio_email(gmail_service, audio_path, target_date) -> bool:
    """Send audio briefing as email attachment."""
    import base64
    from email.mime.audio import MIMEAudio
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from pathlib import Path

    from ai_daily.config import config

    recipients = config.get_tts_recipients()
    if not recipients:
        logger.warning("No TTS recipients configured, skipping audio email")
        return False

    subject = f"AI Daily Briefing - {target_date.strftime('%B %d, %Y')}"
    body = "Your daily AI audio briefing is attached."

    for recipient in recipients:
        try:
            message = MIMEMultipart()
            message["Subject"] = subject
            message["To"] = recipient
            message["From"] = "me"

            message.attach(MIMEText(body, "plain"))

            # Attach audio file
            audio_data = Path(audio_path).read_bytes()
            audio_part = MIMEAudio(audio_data, _subtype="wav")
            audio_part.add_header(
                "Content-Disposition",
                "attachment",
                filename=f"briefing_{target_date.isoformat()}.wav",
            )
            message.attach(audio_part)

            raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
            gmail_service.users().messages().send(
                userId="me",
                body={"raw": raw},
            ).execute()

            logger.info(f"Audio briefing emailed to {recipient}")
        except Exception as e:
            logger.error(f"Failed to email audio to {recipient}: {e}")
            continue

    return True


# Registry of available jobs
JOBS = {
    "etl": run_etl,
    "newsletter": run_newsletter,
    "github": run_github_newsletter,
    "tts": run_tts,
}
