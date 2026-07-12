# Orchestrator Conventions (`ai_daily/orchestrator/`)

Schedules the recurring jobs (cron expressions), with retries and failure notifications, recording runs
in `job_runs`.

## Jobs

| Job | Schedule | Purpose |
| :-- | :------- | :------ |
| `etl` | `0 */4 * * *` | Collect from all sources + inline enrichment |
| `newsletter` | `0 14 * * *` | Send the daily newsletter |
| `tts` | `0 9 * * *` | Generate the audio briefing |

## Rules

- **Jobs are idempotent.** A retry or an overlapping run must not double-send a newsletter or duplicate
  articles. Guard on state (last-run time, existing `DailySummary`, dedup) — never assume exactly-once.
- Cron expressions are parsed with `croniter`; keep schedules in config, not scattered literals.
- Record every execution in `job_runs` (start, status, error) so failures are visible and debuggable.
- On failure: retry per policy, then emit a failure notification. Don't fail silently and don't retry
  forever — bound the attempts.
- Long-running work is `async` and cancellation-aware; a shutdown mid-job must leave consistent state.
