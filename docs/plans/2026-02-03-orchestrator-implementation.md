# Orchestrator Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement a lightweight internal orchestrator to manage job scheduling, retries, and failure notifications.

**Architecture:** Python module with scheduler (cron-based), executor (exponential backoff retries), and notifier (Gmail alerts). Replaces cron with native scheduling.

**Tech Stack:** Python asyncio, croniter for cron parsing, existing PostgreSQL job_runs table, existing Gmail API.

---

## Task 1: Add croniter dependency

**Files:**
- Modify: `pyproject.toml:10-35`

**Step 1: Add croniter to dependencies**

In `pyproject.toml`, add `croniter>=2.0.0` to the dependencies list:

```toml
dependencies = [
    # Core
    "python-dotenv>=1.0.1",
    "openai>=1.60.2",
    "aiohttp>=3.11.12",
    "requests>=2.32.3",
    "beautifulsoup4>=4.13.3",
    "croniter>=2.0.0",
    # ... rest of dependencies
]
```

**Step 2: Install updated dependencies**

Run: `uv sync`
Expected: croniter installed successfully

**Step 3: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add croniter dependency for cron expression parsing"
```

---

## Task 2: Add orchestrator config to Config class

**Files:**
- Modify: `ai_daily/config.py:50-120`
- Test: `tests/test_orchestrator.py`

**Step 1: Write the failing test**

Create `tests/test_orchestrator.py`:

```python
"""Tests for orchestrator module."""

import os
import pytest


def test_orchestrator_config_defaults():
    """Test OrchestratorConfig has correct defaults."""
    from ai_daily.config import OrchestratorConfig

    cfg = OrchestratorConfig()

    assert cfg.etl_schedule == "0 */4 * * *"
    assert cfg.tts_schedule == "0 9 * * *"
    assert cfg.newsletter_schedule == "0 14 * * *"
    assert cfg.retry_max_attempts == 3
    assert cfg.retry_base_delay == 10.0
    assert cfg.retry_multiplier == 3.0


def test_orchestrator_config_from_env(monkeypatch):
    """Test OrchestratorConfig reads from environment."""
    monkeypatch.setenv("ETL_SCHEDULE", "0 */2 * * *")
    monkeypatch.setenv("RETRY_MAX_ATTEMPTS", "5")

    # Force reimport to pick up new env vars
    from ai_daily import config as config_module
    import importlib
    importlib.reload(config_module)

    cfg = config_module.OrchestratorConfig()

    assert cfg.etl_schedule == "0 */2 * * *"
    assert cfg.retry_max_attempts == 5
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_orchestrator.py::test_orchestrator_config_defaults -v`
Expected: FAIL with "cannot import name 'OrchestratorConfig'"

**Step 3: Implement OrchestratorConfig**

Add to `ai_daily/config.py` after GmailConfig class:

```python
@dataclass
class OrchestratorConfig:
    """Orchestrator scheduling and retry configuration."""

    # Cron schedules
    etl_schedule: str = field(
        default_factory=lambda: os.getenv("ETL_SCHEDULE", "0 */4 * * *")
    )
    tts_schedule: str = field(
        default_factory=lambda: os.getenv("TTS_SCHEDULE", "0 9 * * *")
    )
    newsletter_schedule: str = field(
        default_factory=lambda: os.getenv("NEWSLETTER_SCHEDULE", "0 14 * * *")
    )

    # Retry configuration
    retry_max_attempts: int = field(
        default_factory=lambda: int(os.getenv("RETRY_MAX_ATTEMPTS", "3"))
    )
    retry_base_delay: float = field(
        default_factory=lambda: float(os.getenv("RETRY_BASE_DELAY", "10.0"))
    )
    retry_multiplier: float = field(
        default_factory=lambda: float(os.getenv("RETRY_MULTIPLIER", "3.0"))
    )
```

Also add to Config class:

```python
@dataclass
class Config:
    """Main application configuration container."""

    # Sub-configurations
    db: DatabaseConfig = field(default_factory=DatabaseConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    gmail: GmailConfig = field(default_factory=GmailConfig)
    orchestrator: OrchestratorConfig = field(default_factory=OrchestratorConfig)
    # ... rest unchanged
```

**Step 4: Run test to verify it passes**

Run: `uv run python -m pytest tests/test_orchestrator.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add ai_daily/config.py tests/test_orchestrator.py
git commit -m "feat(orchestrator): add OrchestratorConfig with schedule and retry settings"
```

---

## Task 3: Create orchestrator module structure

**Files:**
- Create: `ai_daily/orchestrator/__init__.py`
- Create: `ai_daily/orchestrator/types.py`

**Step 1: Create orchestrator package**

Create `ai_daily/orchestrator/__init__.py`:

```python
"""Orchestrator module for job scheduling and execution."""

from ai_daily.orchestrator.types import JobContext, RetryConfig

__all__ = ["JobContext", "RetryConfig"]
```

**Step 2: Create types module**

Create `ai_daily/orchestrator/types.py`:

```python
"""Type definitions for orchestrator."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    base_delay: float = 10.0
    multiplier: float = 3.0

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number (0-indexed)."""
        return self.base_delay * (self.multiplier ** attempt)


@dataclass
class JobContext:
    """Context passed to job functions."""

    job_name: str
    run_id: int
    attempt: int
    scheduled_at: datetime
    error: Optional[str] = None
```

**Step 3: Run import test**

Run: `uv run python -c "from ai_daily.orchestrator import JobContext, RetryConfig; print('OK')"`
Expected: OK

**Step 4: Commit**

```bash
git add ai_daily/orchestrator/
git commit -m "feat(orchestrator): add module structure with types"
```

---

## Task 4: Implement executor with retry logic

**Files:**
- Create: `ai_daily/orchestrator/executor.py`
- Modify: `tests/test_orchestrator.py`

**Step 1: Write the failing test**

Add to `tests/test_orchestrator.py`:

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_executor_successful_run():
    """Test executor runs job successfully."""
    from ai_daily.orchestrator.executor import Executor
    from ai_daily.orchestrator.types import RetryConfig

    mock_job = AsyncMock(return_value={"articles_created": 5})

    with patch("ai_daily.orchestrator.executor.get_session") as mock_session:
        mock_session.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_session.return_value.__exit__ = MagicMock(return_value=None)

        executor = Executor(RetryConfig())
        result = await executor.run("test_job", mock_job)

    assert result["success"] is True
    assert result["metrics"] == {"articles_created": 5}
    mock_job.assert_called_once()


@pytest.mark.asyncio
async def test_executor_retry_on_failure():
    """Test executor retries on failure with exponential backoff."""
    from ai_daily.orchestrator.executor import Executor
    from ai_daily.orchestrator.types import RetryConfig

    # Fail twice, succeed on third attempt
    mock_job = AsyncMock(side_effect=[
        Exception("First failure"),
        Exception("Second failure"),
        {"articles_created": 3}
    ])

    with patch("ai_daily.orchestrator.executor.get_session") as mock_session:
        mock_session.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_session.return_value.__exit__ = MagicMock(return_value=None)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            executor = Executor(RetryConfig(base_delay=1.0, multiplier=2.0))
            result = await executor.run("test_job", mock_job)

    assert result["success"] is True
    assert mock_job.call_count == 3
    # Check exponential backoff: 1.0, 2.0
    assert mock_sleep.call_count == 2


@pytest.mark.asyncio
async def test_executor_exhausts_retries():
    """Test executor fails after max retries."""
    from ai_daily.orchestrator.executor import Executor
    from ai_daily.orchestrator.types import RetryConfig

    mock_job = AsyncMock(side_effect=Exception("Always fails"))

    with patch("ai_daily.orchestrator.executor.get_session") as mock_session:
        mock_session.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_session.return_value.__exit__ = MagicMock(return_value=None)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            executor = Executor(RetryConfig(max_attempts=3, base_delay=0.1))
            result = await executor.run("test_job", mock_job)

    assert result["success"] is False
    assert "Always fails" in result["error"]
    assert mock_job.call_count == 3
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_orchestrator.py::test_executor_successful_run -v`
Expected: FAIL with "cannot import name 'Executor'"

**Step 3: Implement Executor**

Create `ai_daily/orchestrator/executor.py`:

```python
"""Job executor with retry logic."""

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from ai_daily.db import JobRun, get_session
from ai_daily.orchestrator.types import JobContext, RetryConfig

logger = logging.getLogger(__name__)


class Executor:
    """Execute jobs with retry logic and tracking."""

    def __init__(self, retry_config: Optional[RetryConfig] = None):
        self.retry_config = retry_config or RetryConfig()

    async def run(
        self,
        job_name: str,
        job_func: Callable,
        scheduled_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Run a job with retries.

        Args:
            job_name: Name of the job for tracking.
            job_func: Async function to execute.
            scheduled_at: When the job was scheduled (for context).

        Returns:
            Dict with success, metrics, error, and attempts.
        """
        scheduled_at = scheduled_at or datetime.utcnow()
        last_error: Optional[str] = None
        metrics: Dict[str, Any] = {}

        for attempt in range(self.retry_config.max_attempts):
            run_id = self._create_job_run(job_name, attempt)

            context = JobContext(
                job_name=job_name,
                run_id=run_id,
                attempt=attempt,
                scheduled_at=scheduled_at,
            )

            try:
                logger.info(f"Running job '{job_name}' (attempt {attempt + 1}/{self.retry_config.max_attempts})")
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
        metrics: Optional[Dict] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Update job run with final status."""
        with get_session() as session:
            job_run = session.query(JobRun).filter(JobRun.id == run_id).first()
            if job_run:
                job_run.status = status
                job_run.finished_at = datetime.utcnow()
                job_run.metrics = metrics
                job_run.error_message = error_message
                session.commit()
```

**Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_orchestrator.py -v -k executor`
Expected: All 3 executor tests PASS

**Step 5: Commit**

```bash
git add ai_daily/orchestrator/executor.py tests/test_orchestrator.py
git commit -m "feat(orchestrator): implement Executor with exponential backoff retries"
```

---

## Task 5: Implement notifier for failure alerts

**Files:**
- Create: `ai_daily/orchestrator/notifier.py`
- Modify: `tests/test_orchestrator.py`

**Step 1: Write the failing test**

Add to `tests/test_orchestrator.py`:

```python
from datetime import datetime, timedelta


@pytest.mark.asyncio
async def test_notifier_sends_alert():
    """Test notifier sends email on failure."""
    from ai_daily.orchestrator.notifier import Notifier

    mock_gmail = MagicMock()
    mock_gmail.users.return_value.messages.return_value.send.return_value.execute.return_value = {}

    notifier = Notifier(gmail_service=mock_gmail, recipients=["test@example.com"])

    await notifier.send_failure_alert(
        job_name="etl",
        error="Connection timeout",
        run_id=42,
        started_at=datetime.utcnow() - timedelta(minutes=5),
        attempts=3,
    )

    mock_gmail.users.return_value.messages.return_value.send.assert_called_once()


@pytest.mark.asyncio
async def test_notifier_rate_limits():
    """Test notifier rate limits alerts per job."""
    from ai_daily.orchestrator.notifier import Notifier

    mock_gmail = MagicMock()
    mock_gmail.users.return_value.messages.return_value.send.return_value.execute.return_value = {}

    notifier = Notifier(gmail_service=mock_gmail, recipients=["test@example.com"])

    # First alert should send
    await notifier.send_failure_alert("etl", "Error 1", 1, datetime.utcnow(), 3)
    assert mock_gmail.users.return_value.messages.return_value.send.call_count == 1

    # Second alert for same job within rate limit should not send
    await notifier.send_failure_alert("etl", "Error 2", 2, datetime.utcnow(), 3)
    assert mock_gmail.users.return_value.messages.return_value.send.call_count == 1

    # Alert for different job should send
    await notifier.send_failure_alert("newsletter", "Error 3", 3, datetime.utcnow(), 3)
    assert mock_gmail.users.return_value.messages.return_value.send.call_count == 2
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_orchestrator.py::test_notifier_sends_alert -v`
Expected: FAIL with "cannot import name 'Notifier'"

**Step 3: Implement Notifier**

Create `ai_daily/orchestrator/notifier.py`:

```python
"""Failure notification via email."""

import base64
import logging
from datetime import datetime, timedelta
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
        return datetime.utcnow() - last < timedelta(hours=self.RATE_LIMIT_HOURS)

    def _mark_sent(self, job_name: str) -> None:
        """Mark alert as sent for rate limiting."""
        self._last_alert[job_name] = datetime.utcnow()

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
Failed: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}

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
```

**Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_orchestrator.py -v -k notifier`
Expected: Both notifier tests PASS

**Step 5: Commit**

```bash
git add ai_daily/orchestrator/notifier.py tests/test_orchestrator.py
git commit -m "feat(orchestrator): implement Notifier with rate-limited email alerts"
```

---

## Task 6: Implement scheduler with cron support

**Files:**
- Create: `ai_daily/orchestrator/scheduler.py`
- Modify: `tests/test_orchestrator.py`

**Step 1: Write the failing test**

Add to `tests/test_orchestrator.py`:

```python
from datetime import datetime


def test_scheduler_cron_matching():
    """Test scheduler correctly matches cron expressions."""
    from ai_daily.orchestrator.scheduler import Scheduler

    scheduler = Scheduler(
        schedules={"etl": "0 */4 * * *", "newsletter": "0 14 * * *"},
        executor=MagicMock(),
    )

    # 4:00 AM should match ETL (every 4 hours)
    dt = datetime(2026, 2, 3, 4, 0, 0)
    due = scheduler.get_due_jobs(dt)
    assert "etl" in due
    assert "newsletter" not in due

    # 2:00 PM should match newsletter
    dt = datetime(2026, 2, 3, 14, 0, 0)
    due = scheduler.get_due_jobs(dt)
    assert "newsletter" in due


def test_scheduler_prevents_duplicate_runs():
    """Test scheduler prevents running same job twice in same minute."""
    from ai_daily.orchestrator.scheduler import Scheduler

    scheduler = Scheduler(
        schedules={"etl": "0 */4 * * *"},
        executor=MagicMock(),
    )

    dt = datetime(2026, 2, 3, 4, 0, 0)

    # First call should return the job
    due = scheduler.get_due_jobs(dt)
    assert "etl" in due

    # Mark as recently run
    scheduler.mark_run("etl", dt)

    # Second call at same time should not return the job
    due = scheduler.get_due_jobs(dt)
    assert "etl" not in due
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_orchestrator.py::test_scheduler_cron_matching -v`
Expected: FAIL with "cannot import name 'Scheduler'"

**Step 3: Implement Scheduler**

Create `ai_daily/orchestrator/scheduler.py`:

```python
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
        cron = croniter(cron_expr, dt)
        prev_time = cron.get_prev(datetime)
        # Match if we're within the same minute as the cron trigger
        return (
            prev_time.year == dt.year
            and prev_time.month == dt.month
            and prev_time.day == dt.day
            and prev_time.hour == dt.hour
            and prev_time.minute == dt.minute
        )

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
```

**Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_orchestrator.py -v -k scheduler`
Expected: Both scheduler tests PASS

**Step 5: Commit**

```bash
git add ai_daily/orchestrator/scheduler.py tests/test_orchestrator.py
git commit -m "feat(orchestrator): implement Scheduler with cron expression support"
```

---

## Task 7: Create job functions that wrap existing functionality

**Files:**
- Create: `ai_daily/orchestrator/jobs.py`
- Modify: `ai_daily/orchestrator/__init__.py`

**Step 1: Create jobs module**

Create `ai_daily/orchestrator/jobs.py`:

```python
"""Job definitions for orchestrator."""

import logging
from datetime import date
from typing import Any, Dict

from ai_daily.db import get_session, init_db
from ai_daily.db.seed import seed_sources
from ai_daily.etl import ETLPipeline
from ai_daily.etl.extractors.gmail import GmailExtractor
from ai_daily.orchestrator.types import JobContext
from ai_daily.outputs import NewsletterOutput, TTSBriefingOutput

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


async def run_tts(context: JobContext) -> Dict[str, Any]:
    """Generate TTS audio briefing."""
    logger.info(f"Starting TTS job (run_id={context.run_id})")

    with get_session() as session:
        tts = TTSBriefingOutput()
        audio_path = await tts.generate(session, target_date=date.today())

        return {
            "audio_path": str(audio_path),
            "date": date.today().isoformat(),
        }


# Registry of available jobs
JOBS = {
    "etl": run_etl,
    "newsletter": run_newsletter,
    "tts": run_tts,
}
```

**Step 2: Update __init__.py**

Update `ai_daily/orchestrator/__init__.py`:

```python
"""Orchestrator module for job scheduling and execution."""

from ai_daily.orchestrator.executor import Executor
from ai_daily.orchestrator.jobs import JOBS, run_etl, run_newsletter, run_tts
from ai_daily.orchestrator.notifier import Notifier
from ai_daily.orchestrator.scheduler import Scheduler
from ai_daily.orchestrator.types import JobContext, RetryConfig

__all__ = [
    "Executor",
    "JobContext",
    "JOBS",
    "Notifier",
    "RetryConfig",
    "Scheduler",
    "run_etl",
    "run_newsletter",
    "run_tts",
]
```

**Step 3: Test import**

Run: `uv run python -c "from ai_daily.orchestrator import Scheduler, Executor, JOBS; print('Jobs:', list(JOBS.keys()))"`
Expected: `Jobs: ['etl', 'newsletter', 'tts']`

**Step 4: Commit**

```bash
git add ai_daily/orchestrator/
git commit -m "feat(orchestrator): add job functions wrapping existing pipeline components"
```

---

## Task 8: Add orchestrator CLI commands

**Files:**
- Modify: `ai_daily/cli.py`
- Modify: `tests/test_orchestrator.py`

**Step 1: Write the failing test**

Add to `tests/test_orchestrator.py`:

```python
from click.testing import CliRunner


def test_cli_orchestrator_status():
    """Test orchestrator status command exists."""
    from ai_daily.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["orchestrator", "status"])

    # Should not fail with "No such command"
    assert "No such command" not in result.output


def test_cli_orchestrator_trigger_requires_job():
    """Test orchestrator trigger requires job name."""
    from ai_daily.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["orchestrator", "trigger"])

    assert result.exit_code != 0
    assert "Missing argument" in result.output or "required" in result.output.lower()
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_orchestrator.py::test_cli_orchestrator_status -v`
Expected: FAIL with "No such command 'orchestrator'"

**Step 3: Add orchestrator CLI group**

Add to `ai_daily/cli.py` after the `source` group:

```python
@main.group()
def orchestrator():
    """Manage the job orchestrator."""
    pass


@orchestrator.command("start")
def orchestrator_start():
    """Start the orchestrator scheduler."""
    from ai_daily.config import config
    from ai_daily.etl.extractors.gmail import GmailExtractor
    from ai_daily.orchestrator import Executor, JOBS, Notifier, Scheduler
    from ai_daily.orchestrator.types import RetryConfig

    console.print("[cyan]Starting orchestrator...[/cyan]")

    # Build retry config from settings
    retry_config = RetryConfig(
        max_attempts=config.orchestrator.retry_max_attempts,
        base_delay=config.orchestrator.retry_base_delay,
        multiplier=config.orchestrator.retry_multiplier,
    )

    # Initialize components
    executor = Executor(retry_config)

    # Initialize Gmail for notifications
    try:
        gmail_extractor = GmailExtractor()
        notifier = Notifier(
            gmail_service=gmail_extractor.service,
            recipients=config.recipients,
        )
    except Exception as e:
        console.print(f"[yellow]Gmail not available, notifications disabled: {e}[/yellow]")
        notifier = None

    # Build schedules from config
    schedules = {
        "etl": config.orchestrator.etl_schedule,
        "newsletter": config.orchestrator.newsletter_schedule,
        "tts": config.orchestrator.tts_schedule,
    }

    scheduler = Scheduler(
        schedules=schedules,
        executor=executor,
        notifier=notifier,
        jobs=JOBS,
    )

    console.print(f"[green]Schedules:[/green]")
    for job, cron in schedules.items():
        console.print(f"  {job}: {cron}")

    try:
        asyncio.run(scheduler.start())
    except KeyboardInterrupt:
        console.print("\n[yellow]Orchestrator stopped[/yellow]")


@orchestrator.command("status")
def orchestrator_status():
    """Show orchestrator status and next scheduled runs."""
    from croniter import croniter
    from ai_daily.config import config

    schedules = {
        "etl": config.orchestrator.etl_schedule,
        "newsletter": config.orchestrator.newsletter_schedule,
        "tts": config.orchestrator.tts_schedule,
    }

    table = Table(title="Scheduled Jobs")
    table.add_column("Job", style="cyan")
    table.add_column("Schedule", style="magenta")
    table.add_column("Next Run", style="green")

    now = datetime.utcnow()
    for job_name, cron_expr in schedules.items():
        cron = croniter(cron_expr, now)
        next_run = cron.get_next(datetime)
        table.add_row(job_name, cron_expr, next_run.strftime("%Y-%m-%d %H:%M"))

    console.print(table)

    # Also show recent job runs
    with get_session() as session:
        yesterday = datetime.utcnow() - timedelta(days=1)
        jobs = session.query(JobRun).filter(
            JobRun.started_at >= yesterday
        ).order_by(JobRun.started_at.desc()).limit(10).all()

        if jobs:
            runs_table = Table(title="Recent Runs (Last 24h)")
            runs_table.add_column("Status", style="cyan")
            runs_table.add_column("Job", style="magenta")
            runs_table.add_column("Started", style="green")
            runs_table.add_column("Duration")

            for job in jobs:
                status_icon = "+" if job.status == "success" else "x" if job.status == "failed" else "..."
                status_color = "green" if job.status == "success" else "red" if job.status == "failed" else "yellow"

                duration = ""
                if job.finished_at and job.started_at:
                    delta = job.finished_at - job.started_at
                    duration = f"{delta.total_seconds():.1f}s"

                runs_table.add_row(
                    f"[{status_color}]{status_icon}[/{status_color}]",
                    job.job_name,
                    job.started_at.strftime("%H:%M") if job.started_at else "N/A",
                    duration,
                )

            console.print(runs_table)


@orchestrator.command("trigger")
@click.argument("job_name", type=click.Choice(["etl", "newsletter", "tts"]))
def orchestrator_trigger(job_name: str):
    """Manually trigger a job."""
    from ai_daily.config import config
    from ai_daily.orchestrator import Executor, JOBS
    from ai_daily.orchestrator.types import RetryConfig

    console.print(f"[cyan]Triggering job: {job_name}[/cyan]")

    retry_config = RetryConfig(
        max_attempts=config.orchestrator.retry_max_attempts,
        base_delay=config.orchestrator.retry_base_delay,
        multiplier=config.orchestrator.retry_multiplier,
    )

    executor = Executor(retry_config)
    job_func = JOBS[job_name]

    async def _run():
        result = await executor.run(job_name, job_func)
        return result

    try:
        result = asyncio.run(_run())

        if result["success"]:
            console.print(f"[green]Job completed successfully![/green]")
            if result.get("metrics"):
                console.print(f"Metrics: {result['metrics']}")
        else:
            console.print(f"[red]Job failed: {result.get('error')}[/red]")
            raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)
```

**Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_orchestrator.py -v -k cli`
Expected: Both CLI tests PASS

**Step 5: Commit**

```bash
git add ai_daily/cli.py tests/test_orchestrator.py
git commit -m "feat(orchestrator): add CLI commands for start, status, and trigger"
```

---

## Task 9: Update Docker configuration

**Files:**
- Modify: `Dockerfile`
- Modify: `docker-entrypoint.sh`

**Step 1: Read current files**

Check current Dockerfile and entrypoint for cron references.

**Step 2: Update Dockerfile**

Remove cron installation from Dockerfile. The orchestrator replaces cron.

In `Dockerfile`, remove any lines like:
```dockerfile
RUN apt-get update && apt-get install -y cron
```

**Step 3: Update docker-entrypoint.sh**

Replace cron with orchestrator:

```bash
#!/bin/bash
set -e

# Run migrations
echo "Running database migrations..."
alembic upgrade head

# Seed sources
echo "Seeding sources..."
ai-daily seed

# Start orchestrator in background
echo "Starting orchestrator..."
ai-daily orchestrator start &

# Start API server
echo "Starting API server..."
exec uvicorn ai_daily.api.server:app --host 0.0.0.0 --port 8000
```

**Step 4: Commit**

```bash
git add Dockerfile docker-entrypoint.sh
git commit -m "feat(docker): replace cron with orchestrator in container"
```

---

## Task 10: Update .env.example and README

**Files:**
- Modify: `.env.example`
- Modify: `README.md`

**Step 1: Add orchestrator variables to .env.example**

Add to `.env.example`:

```bash
# Orchestrator Schedules (cron syntax)
ETL_SCHEDULE=0 */4 * * *
TTS_SCHEDULE=0 9 * * *
NEWSLETTER_SCHEDULE=0 14 * * *

# Orchestrator Retry Config
RETRY_MAX_ATTEMPTS=3
RETRY_BASE_DELAY=10
RETRY_MULTIPLIER=3
```

**Step 2: Update README.md**

Add orchestrator section to README:

```markdown
## Orchestrator

The orchestrator manages job scheduling with cron expressions, automatic retries, and failure notifications.

### Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `ETL_SCHEDULE` | ETL job schedule (cron) | `0 */4 * * *` |
| `TTS_SCHEDULE` | TTS job schedule (cron) | `0 9 * * *` |
| `NEWSLETTER_SCHEDULE` | Newsletter schedule (cron) | `0 14 * * *` |
| `RETRY_MAX_ATTEMPTS` | Max retry attempts | `3` |
| `RETRY_BASE_DELAY` | Initial retry delay (seconds) | `10` |
| `RETRY_MULTIPLIER` | Delay multiplier | `3` |

### CLI Commands

```bash
# Start orchestrator (foreground)
ai-daily orchestrator start

# Show scheduled jobs and recent runs
ai-daily orchestrator status

# Manually trigger a job
ai-daily orchestrator trigger etl
ai-daily orchestrator trigger newsletter
ai-daily orchestrator trigger tts
```

### Retry Behavior

Jobs retry with exponential backoff:
- Attempt 1: immediate
- Attempt 2: after 10 seconds
- Attempt 3: after 30 seconds (10 * 3)

On final failure, an email alert is sent to configured recipients.
```

**Step 3: Commit**

```bash
git add .env.example README.md
git commit -m "docs: add orchestrator configuration and usage documentation"
```

---

## Task 11: Run full test suite and verify

**Files:**
- None (verification only)

**Step 1: Run all tests**

Run: `uv run python -m pytest tests/ -v`
Expected: All tests pass

**Step 2: Test orchestrator status command**

Run: `uv run ai-daily orchestrator status`
Expected: Shows scheduled jobs table

**Step 3: Commit any remaining changes**

```bash
git status
# If any uncommitted changes, commit them
```

---

## Summary

After completing all tasks, the orchestrator module provides:

1. **Scheduler** - Cron-based job scheduling with minute-level precision
2. **Executor** - Retry logic with exponential backoff (10s, 30s, 90s)
3. **Notifier** - Email alerts on final failure with rate limiting
4. **Jobs** - ETL, Newsletter, TTS wrapped as async functions
5. **CLI** - Commands for start, status, and manual triggers
6. **Docker** - Orchestrator replaces cron in container

The orchestrator runs as a single process, checking every minute for due jobs, and integrates with the existing PostgreSQL job_runs table for tracking.
