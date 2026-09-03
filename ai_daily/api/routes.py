"""API route handlers."""

import asyncio
import json
import logging
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ai_daily.db import Article, DailySummary, JobRun, Source, get_session

logger = logging.getLogger(__name__)


def escape_like_wildcards(value: str) -> str:
    """Escape SQL LIKE wildcard characters (% and _) in user input.

    This prevents users from injecting wildcards that could affect query behavior.
    """
    return value.replace("%", r"\%").replace("_", r"\_")


router = APIRouter()


# Pydantic models for responses
class ArticleResponse(BaseModel):
    id: int
    title: str
    content: str
    url: str | None
    author: str | None
    topic: str | None
    tags: list[str] | None
    published_at: datetime | None
    ingested_at: datetime | None
    source_name: str | None = None
    summary: str | None
    category: str | None
    is_ai_related: bool | None
    enriched_at: datetime | None
    is_duplicate: bool = False
    duplicate_of_id: int | None

    model_config = ConfigDict(from_attributes=True)


class SummaryResponse(BaseModel):
    date: datetime
    summary_text: str | None
    key_facts: Any | None  # JSONB in DB, can be dict or list
    article_ids: list[int] | None
    created_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class SourceResponse(BaseModel):
    id: int
    type: str
    name: str
    config: dict | None
    enabled: bool
    created_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class SourceCreate(BaseModel):
    type: str
    name: str
    config: dict | None = None
    enabled: bool = True


class SourceUpdate(BaseModel):
    name: str | None = None
    config: dict | None = None
    enabled: bool | None = None


class SourceTestResult(BaseModel):
    success: bool
    message: str | None = None
    preview: dict | None = None


class JobResponse(BaseModel):
    id: int
    job_name: str
    started_at: datetime
    finished_at: datetime | None
    status: str | None
    metrics: dict | None
    error_message: str | None

    model_config = ConfigDict(from_attributes=True)


class SystemStatus(BaseModel):
    database: str
    total_articles: int
    articles_today: int
    active_sources: int
    enriched_articles: int = 0
    ai_related_articles: int = 0
    duplicate_articles: int = 0
    last_job: dict | None = None
    next_runs: dict | None = None


# Dependency for DB session
def get_db():
    with get_session() as session:
        yield session


# Article endpoints
@router.get("/articles", response_model=list[ArticleResponse])
def list_articles(
    q: str | None = Query(None, description="Search query"),
    topic: str | None = Query(None, description="Filter by topic"),
    category: str | None = Query(None, description="Filter by category"),
    is_ai_related: bool | None = Query(None, description="Filter by AI relevance"),
    is_duplicate: bool | None = Query(None, description="Filter by duplicate status"),
    source_type: str | None = Query(
        None, description="Filter by source type (rss, newsletter, github, crawler)"
    ),
    exclude_source_type: str | None = Query(None, description="Exclude source type"),
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    limit: int = Query(20, le=100),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    """List articles with optional filters."""
    try:
        stmt = select(Article).join(Source, Article.source_id == Source.id)

        if q:
            escaped_q = escape_like_wildcards(q)
            stmt = stmt.where(
                or_(
                    Article.title.ilike(f"%{escaped_q}%", escape="\\"),
                    Article.content.ilike(f"%{escaped_q}%", escape="\\"),
                )
            )

        if topic:
            stmt = stmt.where(Article.topic == topic)

        if category:
            stmt = stmt.where(Article.category == category)

        if is_ai_related is not None:
            stmt = stmt.where(Article.is_ai_related == is_ai_related)

        if is_duplicate is not None:
            stmt = stmt.where(Article.is_duplicate == is_duplicate)

        if source_type:
            stmt = stmt.where(Source.type == source_type)

        if exclude_source_type:
            stmt = stmt.where(Source.type != exclude_source_type)

        if from_date:
            stmt = stmt.where(
                Article.published_at >= datetime.combine(from_date, datetime.min.time(), tzinfo=UTC)
            )

        if to_date:
            stmt = stmt.where(
                Article.published_at <= datetime.combine(to_date, datetime.max.time(), tzinfo=UTC)
            )

        stmt = stmt.order_by(Article.published_at.desc()).offset(offset).limit(limit)

        articles = db.execute(stmt).scalars().all()

        # Populate source_name from the relationship
        results = []
        for article in articles:
            resp = ArticleResponse.model_validate(article)
            if article.source:
                resp.source_name = article.source.name
            results.append(resp)
        return results
    except SQLAlchemyError as e:
        logger.error(f"Database error in list_articles: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred") from e


@router.get("/articles/{article_id}", response_model=ArticleResponse)
def get_article(article_id: int, db: Session = Depends(get_db)):
    """Get a single article by ID."""
    try:
        article = db.get(Article, article_id)
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")
        return article
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_article: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred") from e


@router.get("/search", response_model=list[ArticleResponse])
async def semantic_search(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, le=50),
    db: Session = Depends(get_db),
):
    """Semantic search: embed the query and rank by pgvector cosine distance.

    Falls back to keyword ILIKE search if embedding fails (e.g. LLM API down).
    """
    try:
        from ai_daily.etl.transformers.embedder import Embedder

        embedding = await Embedder().embed(q)
        stmt = (
            select(Article)
            .where(
                Article.embedding.isnot(None),
                Article.is_duplicate.is_(False),
            )
            .order_by(Article.embedding.cosine_distance(embedding))
            .limit(limit)
        )
        return db.execute(stmt).scalars().all()
    except SQLAlchemyError as e:
        logger.error(f"Database error in semantic_search: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred") from e
    except Exception as e:
        logger.warning(f"Embedding failed, keyword fallback for search: {e}")
        escaped_q = escape_like_wildcards(q)
        stmt = (
            select(Article)
            .where(
                or_(
                    Article.title.ilike(f"%{escaped_q}%", escape="\\"),
                    Article.content.ilike(f"%{escaped_q}%", escape="\\"),
                )
            )
            .order_by(Article.published_at.desc())
            .limit(limit)
        )
        return db.execute(stmt).scalars().all()


# Summary endpoints
@router.get("/summary/{target_date}", response_model=SummaryResponse)
def get_summary(target_date: date, db: Session = Depends(get_db)):
    """Get daily summary for a specific date."""
    try:
        stmt = select(DailySummary).where(
            DailySummary.date == datetime.combine(target_date, datetime.min.time(), tzinfo=UTC)
        )
        summary = db.execute(stmt).scalar_one_or_none()

        if not summary:
            raise HTTPException(status_code=404, detail="Summary not found for this date")

        return summary
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_summary: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred") from e


@router.get("/summaries", response_model=list[SummaryResponse])
def list_summaries(
    limit: int = Query(20, le=100),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    """List daily summaries."""
    try:
        stmt = select(DailySummary).order_by(DailySummary.date.desc()).offset(offset).limit(limit)
        return db.execute(stmt).scalars().all()
    except SQLAlchemyError as e:
        logger.error(f"Database error in list_summaries: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred") from e


# Source endpoints
@router.get("/sources", response_model=list[SourceResponse])
def list_sources(db: Session = Depends(get_db)):
    """List all sources."""
    try:
        return db.execute(select(Source)).scalars().all()
    except SQLAlchemyError as e:
        logger.error(f"Database error in list_sources: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred") from e


@router.get("/sources/{source_id}", response_model=SourceResponse)
def get_source(source_id: int, db: Session = Depends(get_db)):
    """Get a single source by ID."""
    try:
        source = db.get(Source, source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")
        return source
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_source: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred") from e


@router.post("/sources", response_model=SourceResponse, status_code=201)
def create_source(source_data: SourceCreate, db: Session = Depends(get_db)):
    """Create a new source."""
    try:
        source = Source(
            type=source_data.type,
            name=source_data.name,
            config=source_data.config,
            enabled=source_data.enabled,
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        return source
    except SQLAlchemyError as e:
        logger.error(f"Database error in create_source: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error occurred") from e


@router.put("/sources/{source_id}", response_model=SourceResponse)
def update_source(source_id: int, source_data: SourceUpdate, db: Session = Depends(get_db)):
    """Update an existing source."""
    try:
        source = db.get(Source, source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")

        if source_data.name is not None:
            source.name = source_data.name
        if source_data.config is not None:
            source.config = source_data.config
        if source_data.enabled is not None:
            source.enabled = source_data.enabled

        db.commit()
        db.refresh(source)
        return source
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error in update_source: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error occurred") from e


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(source_id: int, db: Session = Depends(get_db)):
    """Delete a source."""
    try:
        source = db.get(Source, source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")

        db.delete(source)
        db.commit()
        return None
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error in delete_source: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error occurred") from e


@router.patch("/sources/{source_id}/toggle", response_model=SourceResponse)
def toggle_source(source_id: int, db: Session = Depends(get_db)):
    """Toggle a source's enabled/disabled status."""
    try:
        source = db.get(Source, source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")

        source.enabled = not source.enabled
        db.commit()
        db.refresh(source)
        return source
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error in toggle_source: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error occurred") from e


def _test_rss_source(config: dict | None) -> SourceTestResult:
    """Test an RSS source by parsing the feed URL."""
    if not config or not config.get("url"):
        return SourceTestResult(success=False, message="Missing URL in config")
    try:
        import feedparser

        feed = feedparser.parse(config["url"])
        if feed.bozo and not feed.entries:
            return SourceTestResult(
                success=False, message=f"Failed to parse feed: {feed.bozo_exception}"
            )
        return SourceTestResult(
            success=True,
            preview={
                "feed_title": feed.feed.get("title", "Unknown"),
                "entry_count": len(feed.entries),
                "sample_titles": [e.get("title", "")[:100] for e in feed.entries[:3]],
            },
        )
    except Exception as e:
        return SourceTestResult(success=False, message=str(e))


def _test_newsletter_source(config: dict | None) -> SourceTestResult:
    """Test a newsletter source by validating the email format."""
    if not config or not config.get("email"):
        return SourceTestResult(success=False, message="Missing email in config")
    import re

    email = config["email"]
    # Basic email validation regex
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(email_pattern, email):
        return SourceTestResult(success=False, message="Invalid email format")
    return SourceTestResult(
        success=True, preview={"email": email, "status": "Email format is valid"}
    )


def _test_crawler_source(config: dict | None) -> SourceTestResult:
    """Test a crawler source by fetching the URL and applying selectors."""
    if not config or not config.get("url"):
        return SourceTestResult(success=False, message="Missing URL in config")
    try:
        import requests
        from bs4 import BeautifulSoup

        url = config["url"]
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        preview_data = {
            "url": url,
            "status_code": response.status_code,
            "title": soup.title.string if soup.title else "No title found",
        }

        # Apply selectors if provided
        if config.get("selector"):
            elements = soup.select(config["selector"])
            preview_data["selector_matches"] = len(elements)
            preview_data["sample_content"] = [el.get_text()[:100] for el in elements[:3]]

        return SourceTestResult(success=True, preview=preview_data)
    except requests.RequestException as e:
        return SourceTestResult(success=False, message=f"Request failed: {e}")
    except Exception as e:
        return SourceTestResult(success=False, message=str(e))


@router.post("/sources/test", response_model=SourceTestResult)
def test_source(source_data: SourceCreate):
    """Test a source configuration without saving it."""
    source_type = source_data.type.lower()

    if source_type == "rss":
        return _test_rss_source(source_data.config)
    elif source_type == "newsletter":
        return _test_newsletter_source(source_data.config)
    elif source_type == "crawler":
        return _test_crawler_source(source_data.config)
    else:
        return SourceTestResult(success=False, message=f"Unknown source type: {source_data.type}")


# Status endpoint
@router.get("/status", response_model=SystemStatus)
def get_status(db: Session = Depends(get_db)):
    """Get system status and stats."""

    from croniter import croniter

    from ai_daily.config import config

    try:
        total_articles = db.execute(select(func.count(Article.id))).scalar() or 0

        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        articles_today = (
            db.execute(
                select(func.count(Article.id)).where(Article.published_at >= today_start)
            ).scalar()
            or 0
        )

        active_sources = (
            db.execute(select(func.count(Source.id)).where(Source.enabled.is_(True))).scalar() or 0
        )

        enriched_articles = (
            db.execute(
                select(func.count(Article.id)).where(Article.enriched_at.isnot(None))
            ).scalar()
            or 0
        )

        ai_related_articles = (
            db.execute(
                select(func.count(Article.id)).where(Article.is_ai_related.is_(True))
            ).scalar()
            or 0
        )

        duplicate_articles = (
            db.execute(
                select(func.count(Article.id)).where(Article.is_duplicate.is_(True))
            ).scalar()
            or 0
        )

        last_job_obj = db.execute(
            select(JobRun).order_by(JobRun.started_at.desc()).limit(1)
        ).scalar_one_or_none()

        last_job = None
        if last_job_obj:
            last_job = {
                "name": last_job_obj.job_name,
                "status": last_job_obj.status,
                "started_at": last_job_obj.started_at.isoformat()
                if last_job_obj.started_at
                else None,
            }

        now = datetime.now(UTC)
        schedules = {
            "etl": config.orchestrator.etl_schedule,
            "newsletter": config.orchestrator.newsletter_schedule,
        }
        next_runs = {}
        for job_name, cron_expr in schedules.items():
            try:
                cron = croniter(cron_expr, now)
                next_runs[job_name] = cron.get_next(datetime).isoformat()
            except Exception:
                pass

        return SystemStatus(
            database="connected",
            total_articles=total_articles,
            articles_today=articles_today,
            active_sources=active_sources,
            enriched_articles=enriched_articles,
            ai_related_articles=ai_related_articles,
            duplicate_articles=duplicate_articles,
            last_job=last_job,
            next_runs=next_runs if next_runs else None,
        )
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_status: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred") from e


# Whitelist endpoints
class WhitelistResponse(BaseModel):
    whitelist: list[str]


class WhitelistAddRequest(BaseModel):
    email: str


def _get_config_path() -> Path:
    """Get the config.json path."""
    from ai_daily.config import config

    return config.config_file


def _read_config() -> dict:
    """Read the whitelist config (personal config.json, else the shipped example)."""
    from ai_daily.config import config

    config_path = config.resolve_config_file()
    if not config_path.exists():
        return {"whitelist": []}
    with open(config_path) as f:
        return json.load(f)


def _write_config(data: dict) -> None:
    """Write config.json file."""
    config_path = _get_config_path()
    with open(config_path, "w") as f:
        json.dump(data, f, indent=2)


@router.get("/whitelist", response_model=WhitelistResponse)
def get_whitelist():
    """Get the list of whitelisted newsletter senders."""
    try:
        config_data = _read_config()
        return WhitelistResponse(whitelist=config_data.get("whitelist", []))
    except Exception as e:
        logger.error(f"Error reading whitelist: {e}")
        raise HTTPException(status_code=500, detail="Failed to read whitelist") from e


@router.post("/whitelist", response_model=WhitelistResponse, status_code=201)
def add_to_whitelist(request: WhitelistAddRequest):
    """Add an email to the whitelist."""
    try:
        email = request.email.strip().lower()
        if not email:
            raise HTTPException(status_code=400, detail="Email cannot be empty")

        config_data = _read_config()
        whitelist = config_data.get("whitelist", [])

        if email in [e.lower() for e in whitelist]:
            raise HTTPException(status_code=409, detail="Email already in whitelist")

        whitelist.append(email)
        config_data["whitelist"] = whitelist
        _write_config(config_data)

        return WhitelistResponse(whitelist=whitelist)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding to whitelist: {e}")
        raise HTTPException(status_code=500, detail="Failed to add to whitelist") from e


@router.delete("/whitelist/{email:path}", status_code=204)
def remove_from_whitelist(email: str):
    """Remove an email from the whitelist."""
    try:
        email_lower = email.strip().lower()
        config_data = _read_config()
        whitelist = config_data.get("whitelist", [])

        # Find and remove (case-insensitive)
        original_len = len(whitelist)
        whitelist = [e for e in whitelist if e.lower() != email_lower]

        if len(whitelist) == original_len:
            raise HTTPException(status_code=404, detail="Email not found in whitelist")

        config_data["whitelist"] = whitelist
        _write_config(config_data)

        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing from whitelist: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove from whitelist") from e


# Job endpoints
@router.get("/jobs", response_model=list[JobResponse])
def list_jobs(
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    """List recent job runs."""
    try:
        stmt = select(JobRun).order_by(JobRun.started_at.desc()).limit(limit)
        return db.execute(stmt).scalars().all()
    except SQLAlchemyError as e:
        logger.error(f"Database error in list_jobs: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred") from e


# Release radar endpoints
class ReleaseResponse(BaseModel):
    id: int
    title: str
    url: str | None
    summary: str | None
    source_name: str | None = None
    ingested_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


@router.get("/releases", response_model=list[ReleaseResponse])
def list_releases(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
):
    """Model-release articles from the last N days (the newsletter's Release Radar)."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    try:
        stmt = (
            select(Article)
            .where(
                Article.ingested_at >= cutoff,
                Article.is_duplicate.is_(False),
                Article.tags.any("model-release"),
            )
            .order_by(Article.ingested_at.desc())
        )
        articles = db.execute(stmt).scalars().all()
        return [
            ReleaseResponse(
                id=a.id,
                title=a.title,
                url=a.url,
                summary=a.summary,
                source_name=a.source.name if a.source else None,
                ingested_at=a.ingested_at,
            )
            for a in articles
        ]
    except SQLAlchemyError as e:
        logger.error(f"Database error in list_releases: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred") from e


class JobTriggerResponse(BaseModel):
    job: str
    status: str


# Keep task references so background jobs aren't garbage-collected mid-run.
_background_jobs: set = set()


@router.post("/jobs/{job_name}/trigger", response_model=JobTriggerResponse, status_code=202)
async def trigger_job(job_name: str):
    """Start a job in the background (same execution path as the CLI trigger)."""
    from ai_daily.config import config as app_config
    from ai_daily.orchestrator import JOBS, Executor
    from ai_daily.orchestrator.types import RetryConfig

    if job_name not in JOBS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown job '{job_name}'. Available: {sorted(JOBS)}",
        )

    executor = Executor(
        RetryConfig(
            max_attempts=app_config.orchestrator.retry_max_attempts,
            base_delay=app_config.orchestrator.retry_base_delay,
            multiplier=app_config.orchestrator.retry_multiplier,
        )
    )
    task = asyncio.create_task(executor.run(job_name, JOBS[job_name]))
    _background_jobs.add(task)
    task.add_done_callback(_background_jobs.discard)
    return JobTriggerResponse(job=job_name, status="started")


# Leaderboard endpoints
class LeaderboardSummary(BaseModel):
    board: str
    captured_at: datetime | None
    row_count: int
    top: list[str]


@router.get("/leaderboards", response_model=list[LeaderboardSummary])
def list_leaderboards(db: Session = Depends(get_db)):
    """Latest snapshot summary for every tracked leaderboard."""
    from ai_daily.db import LeaderboardSnapshot
    from ai_daily.etl.leaderboards import BOARDS

    out = []
    for board in BOARDS:
        snap = db.execute(
            select(LeaderboardSnapshot)
            .where(LeaderboardSnapshot.board == board["key"])
            .order_by(LeaderboardSnapshot.captured_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        out.append(
            LeaderboardSummary(
                board=board["key"],
                captured_at=snap.captured_at if snap else None,
                row_count=snap.row_count if snap else 0,
                top=[r["name"] for r in (snap.rows or [])[:10]] if snap else [],
            )
        )
    return out


@router.get("/leaderboards/{board}")
def get_leaderboard(board: str, limit: int = Query(50, le=300), db: Session = Depends(get_db)):
    """Latest full snapshot of one leaderboard."""
    from ai_daily.db import LeaderboardSnapshot

    snap = db.execute(
        select(LeaderboardSnapshot)
        .where(LeaderboardSnapshot.board == board)
        .order_by(LeaderboardSnapshot.captured_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if not snap:
        raise HTTPException(status_code=404, detail=f"No snapshot for board '{board}'")
    return {
        "board": board,
        "captured_at": snap.captured_at,
        "row_count": snap.row_count,
        "rows": (snap.rows or [])[:limit],
    }


# Audio briefing endpoints
_DAY_RE = r"^\d{4}-\d{2}-\d{2}$"


class BriefingInfo(BaseModel):
    date: str
    size_bytes: int
    has_script: bool


def _briefings_dir() -> Path:
    from ai_daily.config import config as app_config

    return app_config.data_dir / "briefings"


@router.get("/briefings", response_model=list[BriefingInfo])
def list_briefings(limit: int = Query(30, le=100)):
    """Generated audio briefings, newest first."""
    d = _briefings_dir()
    items = []
    if d.exists():
        for wav in sorted(d.glob("*_briefing.wav"), reverse=True)[:limit]:
            day = wav.name.split("_")[0]
            items.append(
                BriefingInfo(
                    date=day,
                    size_bytes=wav.stat().st_size,
                    has_script=(d / f"{day}_script.txt").exists(),
                )
            )
    return items


@router.get("/briefings/{day}/audio")
def briefing_audio(day: str):
    """Stream one briefing WAV (day: YYYY-MM-DD)."""
    from fastapi.responses import FileResponse

    if not re.match(_DAY_RE, day):
        raise HTTPException(status_code=400, detail="day must be YYYY-MM-DD")
    path = _briefings_dir() / f"{day}_briefing.wav"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No briefing for {day}")
    return FileResponse(path, media_type="audio/wav", filename=path.name)


@router.get("/briefings/{day}/script")
def briefing_script(day: str):
    """The spoken script of one briefing."""
    if not re.match(_DAY_RE, day):
        raise HTTPException(status_code=400, detail="day must be YYYY-MM-DD")
    path = _briefings_dir() / f"{day}_script.txt"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No script for {day}")
    return {"date": day, "script": path.read_text()}
