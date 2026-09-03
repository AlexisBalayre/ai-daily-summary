"""Type definitions for orchestrator."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    base_delay: float = 10.0
    multiplier: float = 3.0

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number (0-indexed)."""
        return self.base_delay * (self.multiplier**attempt)


@dataclass
class JobContext:
    """Context passed to job functions."""

    job_name: str
    run_id: int
    attempt: int
    scheduled_at: datetime
    error: str | None = None
