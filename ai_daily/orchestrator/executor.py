"""Job executor with retry logic."""

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from ai_daily.db import JobRun, get_session
from ai_daily.orchestrator.types import JobContext, RetryConfig

logger = logging.getLogger(__name__)


class Executor:
    """Execute jobs with retry logic and tracking."""

    def __init__(self, retry_config: RetryConfig | None = None):
        self.retry_config = retry_config or RetryConfig()

    async def run(
        self,
        job_name: str,
        job_func: Callable,
        scheduled_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Run a job with retries.

        Args:
            job_name: Name of the job for tracking.
            job_func: Async function to execute.
            scheduled_at: When the job was scheduled (for context).

        Returns:
            Dict with success, metrics, error, and attempts.
        """
        scheduled_at = scheduled_at or datetime.now(UTC)
        last_error: str | None = None
        metrics: dict[str, Any] = {}

        for attempt in range(self.retry_config.max_attempts):
            run_id = self._create_job_run(job_name, attempt)

            context = JobContext(
                job_name=job_name,
                run_id=run_id,
                attempt=attempt,
                scheduled_at=scheduled_at,
            )

            try:
                logger.info(
                    f"Running job '{job_name}' (attempt {attempt + 1}/{self.retry_config.max_attempts})"
                )
                result = await job_func(context)
                metrics = result if isinstance(result, dict) else {}

                self._update_job_run(run_id, "success", metrics)
                logger.info(f"Job '{job_name}' completed successfully")

                return {
                    "success": True,
                    "metrics": metrics,
                    "attempts": attempt + 1,
                    "run_id": run_id,
                }

            except Exception as e:
                last_error = str(e)
                logger.error(f"Job '{job_name}' failed (attempt {attempt + 1}): {last_error}")
                self._update_job_run(run_id, "failed", error_message=last_error)

                if attempt < self.retry_config.max_attempts - 1:
                    delay = self.retry_config.get_delay(attempt)
                    logger.info(f"Retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)

        return {
            "success": False,
            "error": last_error,
            "attempts": self.retry_config.max_attempts,
        }

    def _create_job_run(self, job_name: str, attempt: int) -> int:
        """Create a job run record."""
        with get_session() as session:
            job_run = JobRun(
                job_name=f"{job_name}_attempt_{attempt}",
                status="running",
            )
            session.add(job_run)
            session.commit()
            return job_run.id

    def _update_job_run(
        self,
        run_id: int,
        status: str,
        metrics: dict | None = None,
        error_message: str | None = None,
    ) -> None:
        """Update job run with final status."""
        with get_session() as session:
            job_run = session.query(JobRun).filter(JobRun.id == run_id).first()
            if job_run:
                job_run.status = status
                job_run.finished_at = datetime.now(UTC)
                job_run.metrics = metrics
                job_run.error_message = error_message
                session.commit()
