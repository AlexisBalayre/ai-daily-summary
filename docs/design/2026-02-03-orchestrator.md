# Orchestrator Design

**Goal:** Add a lightweight internal orchestrator to manage job scheduling, retries, and failure notifications.

**Architecture:** Python module with scheduler, executor, and notifier components. Replaces cron with native scheduling, adds exponential backoff retries, and sends email alerts on failures.

**Tech Stack:** Python asyncio, croniter (cron parsing), existing PostgreSQL job_runs table, existing Gmail API integration.

---

## Overview

The orchestrator is a lightweight Python module (`ai_daily/orchestrator/`) that handles:
- Cron-based scheduling for three independent jobs (ETL, TTS, Newsletter)
- Job execution with exponential backoff retries
- Failure notifications via email

## Components

```
ai_daily/orchestrator/
├── __init__.py
├── scheduler.py    # Cron-based job scheduling
├── executor.py     # Job execution with retries
└── notifier.py     # Failure alerts via email
```

### Scheduler (`scheduler.py`)

- Runs as a long-lived async process
- Checks every minute if any job is due
- Parses cron expressions from environment variables
- Prevents duplicate runs within the same minute

**Environment variables:**
```bash
ETL_SCHEDULE="0 */4 * * *"        # Every 4 hours
TTS_SCHEDULE="0 9 * * *"          # 9:00 AM daily
NEWSLETTER_SCHEDULE="0 14 * * *"  # 2:00 PM daily
```

### Executor (`executor.py`)

- Runs jobs with retry logic
- Exponential backoff: 3 attempts with delays of 10s, 30s, 90s
- Records all runs in existing `job_runs` table
- Sequential execution (one job at a time to avoid resource contention)

**Configuration:**
```bash
RETRY_MAX_ATTEMPTS=3    # Default: 3
RETRY_BASE_DELAY=10     # Default: 10 seconds
RETRY_MULTIPLIER=3      # Default: 3x (10s, 30s, 90s)
```

**Job context passed to functions:**
```python
@dataclass
class JobContext:
    job_name: str
    run_id: int
    attempt: int
    scheduled_at: datetime
```

### Notifier (`notifier.py`)

- Sends email alerts when a job fails after all retries
- Reuses existing Gmail API integration
- Sends to existing `RECIPIENTS` env var
- Rate limited: max 1 alert per job per hour

**Email format:**
```
Subject: [AI Daily] Job Failed: <job_name>

Job "<job_name>" failed after 3 attempts.

Last error: <error_message>

Run ID: <id>
Started: <timestamp>
Failed: <timestamp>

Check logs: docker compose logs app
```

## Jobs

Three independent jobs with separate schedules:

| Job | Schedule | Function |
|-----|----------|----------|
| `etl` | Every 4 hours | `run_etl_pipeline()` |
| `tts` | 9:00 AM daily | `run_tts_briefing()` |
| `newsletter` | 2:00 PM daily | `run_newsletter()` |

## CLI Integration

New subcommands under `ai-daily orchestrator`:

```bash
# Start orchestrator (foreground process)
ai-daily orchestrator start

# Show next scheduled runs and recent history
ai-daily orchestrator status

# Manually trigger a job (bypasses schedule)
ai-daily orchestrator trigger etl
ai-daily orchestrator trigger newsletter
ai-daily orchestrator trigger tts
```

## Docker Integration

**docker-entrypoint.sh** updated:
```bash
#!/bin/bash
set -e

# Run migrations
alembic upgrade head

# Seed sources
ai-daily seed

# Start orchestrator in background
ai-daily orchestrator start &

# Start API server
exec uvicorn ai_daily.api.server:app --host 0.0.0.0 --port 8000
```

**Dockerfile** changes:
- Remove cron package installation
- Remove crontab file

## Dependencies

Add to `pyproject.toml`:
```toml
"croniter>=2.0.0",  # Cron expression parsing
```

## Configuration Summary

| Variable | Description | Default |
|----------|-------------|---------|
| `ETL_SCHEDULE` | ETL job cron schedule | `0 */4 * * *` |
| `TTS_SCHEDULE` | TTS job cron schedule | `0 9 * * *` |
| `NEWSLETTER_SCHEDULE` | Newsletter job cron schedule | `0 14 * * *` |
| `RETRY_MAX_ATTEMPTS` | Max retry attempts | `3` |
| `RETRY_BASE_DELAY` | Initial retry delay (seconds) | `10` |
| `RETRY_MULTIPLIER` | Delay multiplier per retry | `3` |
