"""API route handlers."""

from datetime import date, datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ai_daily.db import Article, DailySummary, JobRun, Source, get_session

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


class JobResponse(BaseModel):
    id: int
    job_name: str
    started_at: datetime
    finished_at: Optional[datetime]
    status: Optional[str]

    class Config:
        from_attributes = True


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
    stmt = select(Article)

    if q:
        stmt = stmt.where(or_(
            Article.title.ilike(f"%{q}%"),
            Article.content.ilike(f"%{q}%"),
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


@router.get("/articles/{article_id}", response_model=ArticleResponse)
def get_article(article_id: int, db: Session = Depends(get_db)):
    """Get a single article by ID."""
    article = db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


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
    # TODO: Implement proper vector search
    # For now, fall back to keyword search
    stmt = select(Article).where(or_(
        Article.title.ilike(f"%{q}%"),
        Article.content.ilike(f"%{q}%"),
    )).order_by(Article.published_at.desc()).limit(limit)

    return db.execute(stmt).scalars().all()


# Summary endpoints
@router.get("/summary/{target_date}", response_model=SummaryResponse)
def get_summary(target_date: date, db: Session = Depends(get_db)):
    """Get daily summary for a specific date."""
    stmt = select(DailySummary).where(
        DailySummary.date == datetime.combine(target_date, datetime.min.time())
    )
    summary = db.execute(stmt).scalar_one_or_none()

    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found for this date")

    return summary


# Source endpoints
@router.get("/sources", response_model=List[SourceResponse])
def list_sources(db: Session = Depends(get_db)):
    """List all sources."""
    return db.execute(select(Source)).scalars().all()


# Job endpoints
@router.get("/jobs", response_model=List[JobResponse])
def list_jobs(
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    """List recent job runs."""
    stmt = select(JobRun).order_by(JobRun.started_at.desc()).limit(limit)
    return db.execute(stmt).scalars().all()
