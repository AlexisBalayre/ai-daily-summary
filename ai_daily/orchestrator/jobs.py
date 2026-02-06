"""Job definitions for orchestrator."""

import logging
from datetime import date
from typing import Any, Dict

from ai_daily.db import get_session, init_db
from ai_daily.db.seed import seed_sources
from ai_daily.etl import ETLPipeline
from ai_daily.etl.extractors.gmail import GmailExtractor
from ai_daily.orchestrator.types import JobContext
from ai_daily.outputs import GitHubNewsletterOutput, NewsletterOutput, TTSBriefingOutput

logger = logging.getLogger(__name__)


async def run_etl(context: JobContext) -> Dict[str, Any]:
    """Run ETL pipeline for all sources."""
    logger.info(f"Starting ETL job (run_id={context.run_id})")

    # Ensure database is ready
    init_db()
    seed_sources()

    pipeline = ETLPipeline()
    metrics = await pipeline.run_all()

    logger.info(f"ETL complete: {metrics}")
    return metrics


async def run_newsletter(context: JobContext) -> Dict[str, Any]:
    """Generate and send newsletter."""
    logger.info(f"Starting newsletter job (run_id={context.run_id})")

    with get_session() as session:
        gmail_extractor = GmailExtractor()
        newsletter = NewsletterOutput(gmail_service=gmail_extractor.service)

        success = await newsletter.send(session, target_date=date.today())

        return {
            "sent": success,
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
