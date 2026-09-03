"""Job definitions for orchestrator."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from ai_daily.db import Article, get_session, init_db
from ai_daily.db.seed import seed_sources
from ai_daily.etl import ETLPipeline
from ai_daily.etl.extractors.gmail import GmailExtractor
from ai_daily.orchestrator.types import JobContext
from ai_daily.outputs import GitHubNewsletterOutput, NewsletterOutput, TTSBriefingOutput
from ai_daily.outputs.newsletter import MODEL_RELEASE_TAG

logger = logging.getLogger(__name__)


RELEASE_ALERTED_TAG = "release-alerted"


def _alert_new_releases() -> int:
    """Email an instant alert for model-release articles not yet alerted.

    Idempotency lives in the data, not in time windows: each alerted article is
    stamped with RELEASE_ALERTED_TAG, so overlapping ETL runs (manual trigger +
    cron) can never alert the same release twice. Articles older than 24h are
    sealed silently — they only matter for the newsletter's Release Radar.
    """
    with get_session() as session:
        stmt = (
            select(Article)
            .where(
                Article.is_duplicate.is_(False),
                Article.tags.any(MODEL_RELEASE_TAG),
                ~Article.tags.any(RELEASE_ALERTED_TAG),
            )
            .order_by(Article.ingested_at.desc())
        )
        candidates = list(session.execute(stmt).scalars().all())
        if not candidates:
            return 0

        cutoff = datetime.now(UTC) - timedelta(hours=24)
        fresh = [a for a in candidates if a.ingested_at and a.ingested_at >= cutoff]
        stale = [a for a in candidates if a not in fresh]

        # Seal the stale backlog first, regardless of send outcome.
        for a in stale:
            a.tags = [*(a.tags or []), RELEASE_ALERTED_TAG]
        session.commit()

        if not fresh:
            return 0

        gmail = GmailExtractor()
        sent = NewsletterOutput(gmail_service=gmail.service).send_release_alert(fresh)
        if sent:
            # Mark only after a successful send so a failed send retries next run.
            for a in fresh:
                a.tags = [*(a.tags or []), RELEASE_ALERTED_TAG]
            session.commit()
        return len(fresh) if sent else 0


async def run_etl(context: JobContext) -> dict[str, Any]:
    """Run ETL pipeline for all sources."""
    logger.info(f"Starting ETL job (run_id={context.run_id})")

    # Ensure database is ready
    init_db()
    seed_sources()

    pipeline = ETLPipeline()
    metrics = await pipeline.run_all()

    logger.info(f"ETL complete: {metrics}")

    # Instant alert for any model releases not yet alerted (idempotent via tag).
    try:
        alerted = _alert_new_releases()
        if isinstance(metrics, dict):
            metrics = {**metrics, "releases_alerted": alerted}
    except Exception as e:
        logger.warning(f"Release alert step failed (ETL still succeeded): {e}")

    return metrics


async def run_newsletter(context: JobContext) -> dict[str, Any]:
    """Generate and send the newsletter with the spoken briefing attached."""
    logger.info(f"Starting newsletter job (run_id={context.run_id})")

    with get_session() as session:
        # Generate the audio briefing first, but best-effort: a TTS failure must
        # never block the newsletter itself. On failure we send without audio.
        audio_path = None
        try:
            tts = TTSBriefingOutput()
            audio_path, _ = await tts.generate(session, target_date=datetime.now(UTC).date())
        except Exception as e:
            logger.warning(f"Briefing audio unavailable, sending newsletter without it: {e}")

        gmail_extractor = GmailExtractor()
        newsletter = NewsletterOutput(gmail_service=gmail_extractor.service)

        success = await newsletter.send(
            session, target_date=datetime.now(UTC).date(), audio_path=audio_path
        )

        return {
            "sent": success,
            "audio_attached": audio_path is not None,
            "date": datetime.now(UTC).date().isoformat(),
        }


async def run_github_newsletter(context: JobContext) -> dict[str, Any]:
    """Generate and send GitHub trending repos newsletter."""
    logger.info(f"Starting GitHub newsletter job (run_id={context.run_id})")

    with get_session() as session:
        gmail_extractor = GmailExtractor()
        github_newsletter = GitHubNewsletterOutput(gmail_service=gmail_extractor.service)

        success = await github_newsletter.send(session)

        return {
            "sent": success,
            "date": datetime.now(UTC).date().isoformat(),
        }


async def run_tts(context: JobContext) -> dict[str, Any]:
    """Generate the TTS audio briefing, copy it to the sync directory, and email it."""
    logger.info(f"Starting TTS job (run_id={context.run_id})")

    with get_session() as session:
        tts = TTSBriefingOutput()
        audio_path, sync_path = await tts.generate(session, target_date=datetime.now(UTC).date())

        # Send audio by email
        email_sent = False
        try:
            gmail_extractor = GmailExtractor()
            email_sent = _send_audio_email(
                gmail_service=gmail_extractor.service,
                audio_path=audio_path,
                target_date=datetime.now(UTC).date(),
            )
        except Exception as e:
            logger.warning(f"Failed to email audio briefing: {e}")

        return {
            "audio_path": str(audio_path),
            "sync_path": str(sync_path) if sync_path else None,
            "email_sent": email_sent,
            "date": datetime.now(UTC).date().isoformat(),
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


async def run_leaderboards(context: JobContext) -> dict[str, Any]:
    """Capture all model leaderboards, diff against previous snapshots, alert."""
    logger.info(f"Starting leaderboards job (run_id={context.run_id})")
    from ai_daily.etl.leaderboards import capture_all

    init_db()
    with get_session() as session:
        result = await capture_all(session)

    changes = result.get("changes") or {}
    if changes:
        try:
            gmail = GmailExtractor()
            _send_leaderboard_alert(gmail.service, changes)
            result["alerted"] = True
        except Exception as e:
            logger.warning(f"Leaderboard alert failed (capture still stored): {e}")
            result["alerted"] = False
    return result


def _send_leaderboard_alert(gmail_service, changes: dict[str, Any]) -> None:
    """Email a digest of leaderboard changes (new/dropped models, rank moves)."""
    import base64
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from html import escape

    from ai_daily.config import config

    recipients = config.get_newsletter_recipients()
    if not recipients:
        logger.warning("No recipients configured for leaderboard alert")
        return

    n_boards = len(changes)
    subject = f"📊 Leaderboard changes on {n_boards} board{'s' if n_boards > 1 else ''}"

    sections_html, text_lines = "", ["Leaderboard changes:", ""]
    for board, diff in changes.items():
        url = escape(diff.get("url", "#"))
        parts_html, parts_text = "", []
        if diff.get("added"):
            names = ", ".join(escape(n) for n in diff["added"])
            parts_html += f'<p style="margin:4px 0;"><b>New:</b> {names}</p>'
            parts_text.append(f"  new: {', '.join(diff['added'])}")
        if diff.get("removed"):
            names = ", ".join(escape(n) for n in diff["removed"])
            parts_html += f'<p style="margin:4px 0;color:#71717a;"><b>Dropped:</b> {names}</p>'
            parts_text.append(f"  dropped: {', '.join(diff['removed'])}")
        for mv in diff.get("moves", []):
            arrow = "↑" if mv["to"] < mv["from"] else "↓"
            parts_html += (
                f'<p style="margin:4px 0;">{arrow} {escape(mv["name"])}: '
                f"#{mv['from']} → #{mv['to']}</p>"
            )
            parts_text.append(f"  {arrow} {mv['name']}: #{mv['from']} -> #{mv['to']}")
        sections_html += (
            f'<div style="margin:0 0 18px;padding:14px 16px;border:1px solid #e4e4e7;'
            f'border-radius:8px;font-family:Inter,-apple-system,sans-serif;font-size:14px;">'
            f'<div style="font-weight:600;margin-bottom:6px;"><a href="{url}" '
            f'style="color:#18181b;text-decoration:none;">{escape(board)}</a></div>{parts_html}</div>'
        )
        text_lines.append(board)
        text_lines.extend(parts_text)
        text_lines.append("")

    html = f'<div style="max-width:600px;margin:0 auto;padding:24px;">{sections_html}</div>'
    text = "\n".join(text_lines)

    for recipient in recipients:
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["To"] = recipient
        message["From"] = "me"
        message.attach(MIMEText(text, "plain"))
        message.attach(MIMEText(html, "html"))
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        try:
            gmail_service.users().messages().send(userId="me", body={"raw": raw}).execute()
        except Exception as e:
            logger.error(f"Failed to send leaderboard alert to {recipient}: {e}")
    logger.info(f"Leaderboard alert sent for {n_boards} board(s)")


# Registry of available jobs
JOBS = {
    "etl": run_etl,
    "newsletter": run_newsletter,
    "github": run_github_newsletter,
    "tts": run_tts,
    "leaderboards": run_leaderboards,
}
