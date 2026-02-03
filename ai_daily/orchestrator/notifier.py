"""Failure notification via email."""

import base64
import logging
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class Notifier:
    """Send failure notifications via Gmail."""

    RATE_LIMIT_HOURS = 1

    def __init__(
        self,
        gmail_service=None,
        recipients: Optional[List[str]] = None,
    ):
        self.gmail_service = gmail_service
        self.recipients = recipients or []
        self._last_alert: Dict[str, datetime] = {}

    def _is_rate_limited(self, job_name: str) -> bool:
        """Check if alerts for this job are rate limited."""
        last = self._last_alert.get(job_name)
        if last is None:
            return False
        now = datetime.now(timezone.utc)
        # Handle both naive and aware datetimes for comparison
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        return now - last < timedelta(hours=self.RATE_LIMIT_HOURS)

    def _mark_sent(self, job_name: str) -> None:
        """Mark alert as sent for rate limiting."""
        self._last_alert[job_name] = datetime.now(timezone.utc)

    async def send_failure_alert(
        self,
        job_name: str,
        error: str,
        run_id: int,
        started_at: datetime,
        attempts: int,
    ) -> bool:
        """Send failure alert email.

        Args:
            job_name: Name of the failed job.
            error: Error message.
            run_id: Job run ID.
            started_at: When the job started.
            attempts: Number of attempts made.

        Returns:
            True if alert was sent, False if rate limited or failed.
        """
        if not self.gmail_service:
            logger.warning("Gmail service not configured, skipping alert")
            return False

        if not self.recipients:
            logger.warning("No recipients configured, skipping alert")
            return False

        if self._is_rate_limited(job_name):
            logger.info(f"Alert for job '{job_name}' rate limited, skipping")
            return False

        subject = f"[AI Daily] Job Failed: {job_name}"
        body = f"""Job "{job_name}" failed after {attempts} attempts.

Last error: {error}

Run ID: {run_id}
Started: {started_at.strftime('%Y-%m-%d %H:%M:%S')}
Failed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}

Check logs: docker compose logs app
"""

        for recipient in self.recipients:
            try:
                message = MIMEText(body, "plain")
                message["Subject"] = subject
                message["To"] = recipient
                message["From"] = "me"

                raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
                self.gmail_service.users().messages().send(
                    userId="me",
                    body={"raw": raw}
                ).execute()

                logger.info(f"Failure alert sent to {recipient}")
            except Exception as e:
                logger.error(f"Failed to send alert to {recipient}: {e}")
                continue

        self._mark_sent(job_name)
        return True
