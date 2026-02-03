"""Cron-based job scheduler."""

import asyncio
import logging
from datetime import datetime
from typing import Callable, Dict, List, Optional

from croniter import croniter

from ai_daily.orchestrator.executor import Executor
from ai_daily.orchestrator.notifier import Notifier

logger = logging.getLogger(__name__)


class Scheduler:
    """Schedule and dispatch jobs based on cron expressions."""

    def __init__(
        self,
        schedules: Dict[str, str],
        executor: Executor,
        notifier: Optional[Notifier] = None,
        jobs: Optional[Dict[str, Callable]] = None,
    ):
        self.schedules = schedules
        self.executor = executor
        self.notifier = notifier
        self.jobs = jobs or {}
        self._last_run: Dict[str, datetime] = {}
        self._running = False

    def get_due_jobs(self, now: Optional[datetime] = None) -> List[str]:
        """Get list of jobs that are due to run.

        Args:
            now: Current time (defaults to utcnow).

        Returns:
            List of job names that should run.
        """
        now = now or datetime.utcnow()
        due = []

        for job_name, cron_expr in self.schedules.items():
            if self._is_recently_run(job_name, now):
                continue

            if self._cron_matches(cron_expr, now):
                due.append(job_name)

        return due

    def _cron_matches(self, cron_expr: str, dt: datetime) -> bool:
        """Check if datetime matches cron expression."""
        # Use croniter.match to check if the datetime matches the cron expression
        return croniter.match(cron_expr, dt)

    def _is_recently_run(self, job_name: str, now: datetime) -> bool:
        """Check if job was run in the current minute."""
        last = self._last_run.get(job_name)
        if last is None:
            return False
        return (
            last.year == now.year
            and last.month == now.month
            and last.day == now.day
            and last.hour == now.hour
            and last.minute == now.minute
        )

    def mark_run(self, job_name: str, at: Optional[datetime] = None) -> None:
        """Mark job as run at given time."""
        self._last_run[job_name] = at or datetime.utcnow()

    def register_job(self, name: str, func: Callable) -> None:
        """Register a job function."""
        self.jobs[name] = func

    async def run_job(self, job_name: str) -> Dict:
        """Run a single job immediately."""
        if job_name not in self.jobs:
            raise ValueError(f"Unknown job: {job_name}")

        job_func = self.jobs[job_name]
        result = await self.executor.run(job_name, job_func)

        if not result["success"] and self.notifier:
            await self.notifier.send_failure_alert(
                job_name=job_name,
                error=result.get("error", "Unknown error"),
                run_id=result.get("run_id", 0),
                started_at=datetime.utcnow(),
                attempts=result.get("attempts", 0),
            )

        return result

    async def tick(self) -> List[str]:
        """Check for due jobs and run them. Returns list of jobs run."""
        now = datetime.utcnow()
        due_jobs = self.get_due_jobs(now)
        run_jobs = []

        for job_name in due_jobs:
            if job_name in self.jobs:
                logger.info(f"Job '{job_name}' is due, starting...")
                self.mark_run(job_name, now)
                await self.run_job(job_name)
                run_jobs.append(job_name)
            else:
                logger.warning(f"Job '{job_name}' is due but not registered")

        return run_jobs

    async def start(self) -> None:
        """Start the scheduler loop (runs until stopped)."""
        self._running = True
        logger.info("Scheduler started")
        logger.info(f"Registered jobs: {list(self.jobs.keys())}")
        logger.info(f"Schedules: {self.schedules}")

        while self._running:
            try:
                await self.tick()
            except Exception as e:
                logger.error(f"Scheduler tick error: {e}")

            await asyncio.sleep(60)  # Check every minute

    def stop(self) -> None:
        """Stop the scheduler loop."""
        self._running = False
        logger.info("Scheduler stopped")
