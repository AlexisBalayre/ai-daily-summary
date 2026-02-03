"""CLI entry point for AI Daily Summary."""

import asyncio
from datetime import datetime, timedelta

import click
from rich.console import Console
from rich.table import Table

from ai_daily.db import Article, JobRun, Source, get_session, init_db

console = Console()


@click.group()
def main():
    """AI Daily Summary - Data platform for AI news aggregation."""
    pass


@main.command()
def init():
    """Initialize the database."""
    init_db()
    console.print("[green]Database initialized successfully![/green]")


@main.command()
def seed():
    """Seed database with initial sources from config.json."""
    from ai_daily.db.seed import seed_sources
    seed_sources()
    console.print("[green]Database seeded successfully![/green]")


@main.command()
@click.argument("job_type", type=click.Choice(["gmail", "github", "crawlers", "all"]))
def run(job_type: str):
    """Run ETL pipeline for specified source type."""
    from ai_daily.etl import ETLPipeline

    async def _run():
        pipeline = ETLPipeline()

        if job_type == "all":
            metrics = await pipeline.run_all()
        else:
            type_map = {"gmail": "newsletter", "github": "github", "crawlers": "crawler"}
            metrics = await pipeline.run_all(source_types=[type_map[job_type]])

        console.print(f"[green]ETL completed![/green]")
        console.print(f"  Processed: {metrics['articles_processed']}")
        console.print(f"  Created: {metrics['articles_created']}")
        console.print(f"  Duplicates: {metrics['duplicates_skipped']}")

    try:
        asyncio.run(_run())
    except Exception as e:
        console.print(f"[red]ETL pipeline failed: {e}[/red]")
        raise SystemExit(1)


@main.command()
def status():
    """Show recent job runs."""
    with get_session() as session:
        yesterday = datetime.utcnow() - timedelta(days=1)
        jobs = session.query(JobRun).filter(
            JobRun.started_at >= yesterday
        ).order_by(JobRun.started_at.desc()).limit(20).all()

        if not jobs:
            console.print("[yellow]No jobs in the last 24 hours[/yellow]")
            return

        table = Table(title="Job Runs (Last 24h)")
        table.add_column("Status", style="cyan")
        table.add_column("Job", style="magenta")
        table.add_column("Started", style="green")
        table.add_column("Duration")
        table.add_column("Metrics")

        for job in jobs:
            job_status = job.status or "unknown"
            status_icon = "+" if job_status == "success" else "x" if job_status == "failed" else "..."
            status_color = "green" if job_status == "success" else "red" if job_status == "failed" else "yellow"

            duration = ""
            if job.finished_at and job.started_at:
                delta = job.finished_at - job.started_at
                duration = f"{delta.total_seconds():.1f}s"

            metrics_str = ""
            if job.metrics:
                if "articles_created" in job.metrics:
                    metrics_str = f"{job.metrics['articles_created']} articles"

            started_str = job.started_at.strftime("%H:%M") if job.started_at else "N/A"

            table.add_row(
                f"[{status_color}]{status_icon}[/{status_color}]",
                job.job_name,
                started_str,
                duration,
                metrics_str,
            )

        console.print(table)


@main.command()
@click.argument("query")
def search(query: str):
    """Search articles by keyword."""
    from sqlalchemy import or_

    with get_session() as session:
        articles = session.query(Article).filter(
            or_(
                Article.title.ilike(f"%{query}%"),
                Article.content.ilike(f"%{query}%"),
            )
        ).order_by(Article.published_at.desc()).limit(10).all()

        if not articles:
            console.print(f"[yellow]No articles found for '{query}'[/yellow]")
            return

        for article in articles:
            console.print(f"\n[bold cyan]{article.title}[/bold cyan]")
            console.print(f"[dim]{article.topic} | {article.published_at}[/dim]")
            console.print(article.content[:200] + "..." if len(article.content) > 200 else article.content)
            if article.url:
                console.print(f"[blue]{article.url}[/blue]")


@main.command()
def serve():
    """Start the API server."""
    import uvicorn
    uvicorn.run("ai_daily.api.server:app", host="0.0.0.0", port=8000, reload=True)


@main.command("run-daily")
def run_daily():
    """Run the complete daily pipeline (ETL + newsletter + TTS)."""
    from ai_daily.main import run_daily_pipeline
    asyncio.run(run_daily_pipeline())


@main.group()
def source():
    """Manage sources."""
    pass


@source.command("list")
def source_list():
    """List all sources."""
    with get_session() as session:
        sources = session.query(Source).all()

        if not sources:
            console.print("[yellow]No sources configured[/yellow]")
            return

        table = Table(title="Sources")
        table.add_column("ID", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Name", style="green")
        table.add_column("Enabled")

        for src in sources:
            enabled = "+" if src.enabled else "-"
            table.add_row(str(src.id), src.type, src.name, enabled)

        console.print(table)


@source.command("add")
@click.argument("source_type", type=click.Choice(["newsletter", "github", "crawler"]))
@click.argument("name")
@click.option("--config", "-c", help="JSON config string")
def source_add(source_type: str, name: str, config: str = None):
    """Add a new source."""
    import json

    parsed_config = None
    if config:
        try:
            parsed_config = json.loads(config)
        except json.JSONDecodeError as e:
            raise click.BadParameter(f"Invalid JSON config: {e}")

    with get_session() as session:
        src = Source(
            type=source_type,
            name=name,
            config=parsed_config,
            enabled=True,
        )
        session.add(src)
        session.commit()
        console.print(f"[green]Added source: {name} (ID: {src.id})[/green]")


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


if __name__ == "__main__":
    main()
