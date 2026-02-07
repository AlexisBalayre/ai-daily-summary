"""API route handlers."""

import logging
from datetime import date, datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
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
    url: Optional[str]
    topic: Optional[str]
    published_at: Optional[datetime]
    source_name: Optional[str] = None

    class Config:
        from_attributes = True


class SummaryResponse(BaseModel):
    date: datetime
    summary_text: Optional[str]
    key_facts: Optional[Any]  # JSONB in DB, can be dict or list

    class Config:
        from_attributes = True


class SourceResponse(BaseModel):
    id: int
    type: str
    name: str
    enabled: bool

    class Config:
        from_attributes = True


class SourceCreate(BaseModel):
    type: str
    name: str
    config: Optional[dict] = None
    enabled: bool = True


class SourceUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[dict] = None
    enabled: Optional[bool] = None


class SourceTestResult(BaseModel):
    success: bool
    message: Optional[str] = None
    preview: Optional[dict] = None


class JobResponse(BaseModel):
    id: int
    job_name: str
    started_at: datetime
    finished_at: Optional[datetime]
    status: Optional[str]

    class Config:
        from_attributes = True


class SystemStatus(BaseModel):
    database: str
    total_articles: int
    articles_today: int
    active_sources: int
    last_job: Optional[dict] = None
    next_runs: Optional[dict] = None


# Dependency for DB session
def get_db():
    with get_session() as session:
        yield session


# Article endpoints
@router.get("/articles", response_model=List[ArticleResponse])
def list_articles(
    q: Optional[str] = Query(None, description="Search query"),
    topic: Optional[str] = Query(None, description="Filter by topic"),
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    limit: int = Query(20, le=100),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    """List articles with optional filters."""
    try:
        stmt = select(Article)

        if q:
            escaped_q = escape_like_wildcards(q)
            stmt = stmt.where(or_(
                Article.title.ilike(f"%{escaped_q}%", escape="\\"),
                Article.content.ilike(f"%{escaped_q}%", escape="\\"),
            ))

        if topic:
            stmt = stmt.where(Article.topic == topic)

        if from_date:
            stmt = stmt.where(Article.published_at >= datetime.combine(from_date, datetime.min.time()))

        if to_date:
            stmt = stmt.where(Article.published_at <= datetime.combine(to_date, datetime.max.time()))

        stmt = stmt.order_by(Article.published_at.desc()).offset(offset).limit(limit)

        articles = db.execute(stmt).scalars().all()
        return articles
    except SQLAlchemyError as e:
        logger.error(f"Database error in list_articles: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred")


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
        raise HTTPException(status_code=500, detail="Database error occurred")


@router.get("/search", response_model=List[ArticleResponse])
def semantic_search(
    q: str = Query(..., description="Search query"),
    limit: int = Query(10, le=50),
    db: Session = Depends(get_db),
):
    """Semantic search using embeddings.

    Note: Full vector search requires embedding the query.
    This is a placeholder that falls back to keyword search.
    """
    try:
        # TODO: Implement proper vector search
        # For now, fall back to keyword search
        escaped_q = escape_like_wildcards(q)
        stmt = select(Article).where(or_(
            Article.title.ilike(f"%{escaped_q}%", escape="\\"),
            Article.content.ilike(f"%{escaped_q}%", escape="\\"),
        )).order_by(Article.published_at.desc()).limit(limit)

        return db.execute(stmt).scalars().all()
    except SQLAlchemyError as e:
        logger.error(f"Database error in semantic_search: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred")


# Summary endpoints
@router.get("/summary/{target_date}", response_model=SummaryResponse)
def get_summary(target_date: date, db: Session = Depends(get_db)):
    """Get daily summary for a specific date."""
    try:
        stmt = select(DailySummary).where(
            DailySummary.date == datetime.combine(target_date, datetime.min.time())
        )
        summary = db.execute(stmt).scalar_one_or_none()

        if not summary:
            raise HTTPException(status_code=404, detail="Summary not found for this date")

        return summary
    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_summary: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred")


# Source endpoints
@router.get("/sources", response_model=List[SourceResponse])
def list_sources(db: Session = Depends(get_db)):
    """List all sources."""
    try:
        return db.execute(select(Source)).scalars().all()
    except SQLAlchemyError as e:
        logger.error(f"Database error in list_sources: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred")


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
        raise HTTPException(status_code=500, detail="Database error occurred")


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
        raise HTTPException(status_code=500, detail="Database error occurred")


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
        raise HTTPException(status_code=500, detail="Database error occurred")


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
        raise HTTPException(status_code=500, detail="Database error occurred")


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
        raise HTTPException(status_code=500, detail="Database error occurred")


def _test_rss_source(config: Optional[dict]) -> SourceTestResult:
    """Test an RSS source by parsing the feed URL."""
    if not config or not config.get("url"):
        return SourceTestResult(success=False, message="Missing URL in config")
    try:
        import feedparser
        feed = feedparser.parse(config["url"])
        if feed.bozo and not feed.entries:
            return SourceTestResult(success=False, message=f"Failed to parse feed: {feed.bozo_exception}")
        return SourceTestResult(
            success=True,
            preview={
                "feed_title": feed.feed.get("title", "Unknown"),
                "entry_count": len(feed.entries),
                "sample_titles": [e.get("title", "")[:100] for e in feed.entries[:3]]
            }
        )
    except Exception as e:
        return SourceTestResult(success=False, message=str(e))


def _test_newsletter_source(config: Optional[dict]) -> SourceTestResult:
    """Test a newsletter source by validating the email format."""
    if not config or not config.get("email"):
        return SourceTestResult(success=False, message="Missing email in config")
    import re
    email = config["email"]
    # Basic email validation regex
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        return SourceTestResult(success=False, message="Invalid email format")
    return SourceTestResult(
        success=True,
        preview={"email": email, "status": "Email format is valid"}
    )


def _test_crawler_source(config: Optional[dict]) -> SourceTestResult:
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
        return SourceTestResult(
            success=False,
            message=f"Unknown source type: {source_data.type}"
        )


# Status endpoint
@router.get("/status", response_model=SystemStatus)
def get_status(db: Session = Depends(get_db)):
    """Get system status and stats."""
    from datetime import timedelta
    from croniter import croniter
    from ai_daily.config import config

    try:
        total_articles = db.execute(select(func.count(Article.id))).scalar() or 0

        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        articles_today = db.execute(
            select(func.count(Article.id)).where(Article.published_at >= today_start)
        ).scalar() or 0

        active_sources = db.execute(
            select(func.count(Source.id)).where(Source.enabled == True)
        ).scalar() or 0

        last_job_obj = db.execute(
            select(JobRun).order_by(JobRun.started_at.desc()).limit(1)
        ).scalar_one_or_none()

        last_job = None
        if last_job_obj:
            last_job = {
                "name": last_job_obj.job_name,
                "status": last_job_obj.status,
                "started_at": last_job_obj.started_at.isoformat() if last_job_obj.started_at else None
            }

        now = datetime.utcnow()
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
            last_job=last_job,
            next_runs=next_runs if next_runs else None
        )
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_status: {e}")
        raise HTTPException(status_code=500, detail="Database error occurred")


# Job endpoints
@router.get("/jobs", response_model=List[JobResponse])
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
        raise HTTPException(status_code=500, detail="Database error occurred")
