"""Chat endpoint: Gemini function-calling over the platform's own data.

The model answers questions about articles, model releases, leaderboards, and
pipeline state by calling the tool functions below. The google-genai SDK's
automatic function calling executes them and loops until the model produces a
final text answer.
"""

import logging
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from google import genai
from google.genai.types import Content, GenerateContentConfig, Part
from pydantic import BaseModel
from sqlalchemy import select

from ai_daily.api.auth import require_api_token
from ai_daily.config import config
from ai_daily.db import Article, DailySummary, JobRun, LeaderboardSnapshot, get_session

logger = logging.getLogger(__name__)

router = APIRouter()

SYSTEM_PROMPT = """You are the AI-Daily assistant, embedded in the user's personal AI-news
platform dashboard. Answer questions using the provided tools over the user's own data:
ingested articles (with summaries and tags), detected model releases, model-leaderboard
snapshots, daily summaries, and pipeline job status.

Rules:
- Always ground answers in tool results; call tools rather than guessing.
- Cite article titles and include URLs when referencing articles or releases.
- Be concise. Use short paragraphs or bullet lists.
- Today's date is {today}."""


def search_articles(query: str, limit: int = 8) -> list[dict]:
    """Semantic search over ingested articles. Returns title, url, summary, tags, date.

    Args:
        query: Natural-language search query.
        limit: Max results (default 8).
    """
    try:
        client = genai.Client(api_key=config.llm.google_api_key)
        resp = client.models.embed_content(
            model=config.llm.embedding_model,
            contents=query[:8000],
            config={"output_dimensionality": 768},
        )
        embedding = list(resp.embeddings[0].values)
    except Exception as e:
        logger.warning(f"chat search embedding failed: {e}")
        embedding = None

    with get_session() as session:
        if embedding is not None:
            stmt = (
                select(Article)
                .where(Article.embedding.isnot(None), Article.is_duplicate.is_(False))
                .order_by(Article.embedding.cosine_distance(embedding))
                .limit(min(limit, 20))
            )
        else:
            stmt = (
                select(Article)
                .where(Article.title.ilike(f"%{query}%"))
                .order_by(Article.ingested_at.desc())
                .limit(min(limit, 20))
            )
        return [
            {
                "title": a.title,
                "url": a.url,
                "summary": a.summary or (a.content or "")[:300],
                "tags": a.tags,
                "source": a.source.name if a.source else None,
                "date": a.ingested_at.isoformat() if a.ingested_at else None,
            }
            for a in session.execute(stmt).scalars().all()
        ]


def latest_releases(days: int = 7) -> list[dict]:
    """New AI model releases detected in the last N days.

    Args:
        days: Lookback window in days (default 7).
    """
    cutoff = datetime.now(UTC) - timedelta(days=days)
    with get_session() as session:
        stmt = (
            select(Article)
            .where(
                Article.ingested_at >= cutoff,
                Article.is_duplicate.is_(False),
                Article.tags.any("model-release"),
            )
            .order_by(Article.ingested_at.desc())
        )
        return [
            {
                "title": a.title,
                "url": a.url,
                "summary": a.summary,
                "source": a.source.name if a.source else None,
                "date": a.ingested_at.isoformat() if a.ingested_at else None,
            }
            for a in session.execute(stmt).scalars().all()
        ]


def get_leaderboard(board: str, top_n: int = 15) -> dict:
    """Latest snapshot of one model leaderboard.

    Args:
        board: One of aa-speech-to-speech, aa-stt-streaming, aa-tts-models,
            arena-text, arena-agent, hf-open-llm, coval-tts, coval-stt.
        top_n: How many top rows to return (default 15).
    """
    with get_session() as session:
        snap = session.execute(
            select(LeaderboardSnapshot)
            .where(LeaderboardSnapshot.board == board)
            .order_by(LeaderboardSnapshot.captured_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if not snap:
            return {"board": board, "error": "no snapshot"}
        return {
            "board": board,
            "captured_at": snap.captured_at.isoformat(),
            "row_count": snap.row_count,
            "top": (snap.rows or [])[:top_n],
        }


def list_leaderboards() -> list[dict]:
    """Summary (top 5 models + capture time) of every tracked leaderboard."""
    from ai_daily.etl.leaderboards import BOARDS

    out = []
    with get_session() as session:
        for b in BOARDS:
            snap = session.execute(
                select(LeaderboardSnapshot)
                .where(LeaderboardSnapshot.board == b["key"])
                .order_by(LeaderboardSnapshot.captured_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            out.append(
                {
                    "board": b["key"],
                    "row_count": snap.row_count if snap else 0,
                    "top": [r["name"] for r in (snap.rows or [])[:5]] if snap else [],
                }
            )
    return out


def daily_summary(target_date: str = "") -> dict:
    """The generated daily news summary. target_date YYYY-MM-DD, empty = today."""
    day = date.fromisoformat(target_date) if target_date else datetime.now(UTC).date()
    with get_session() as session:
        s = session.execute(
            select(DailySummary).where(
                DailySummary.date == datetime.combine(day, datetime.min.time(), tzinfo=UTC)
            )
        ).scalar_one_or_none()
        if not s:
            return {"date": day.isoformat(), "error": "no summary for this date"}
        return {
            "date": day.isoformat(),
            "summary": s.summary_text,
            "key_facts": s.key_facts,
        }


def pipeline_status() -> dict:
    """Recent pipeline job runs (name, status, started_at)."""
    with get_session() as session:
        runs = (
            session.execute(select(JobRun).order_by(JobRun.started_at.desc()).limit(10))
            .scalars()
            .all()
        )
        return {
            "recent_jobs": [
                {
                    "name": r.job_name,
                    "status": r.status,
                    "started_at": r.started_at.isoformat() if r.started_at else None,
                }
                for r in runs
            ]
        }


TOOLS = [
    search_articles,
    latest_releases,
    get_leaderboard,
    list_leaderboards,
    daily_summary,
    pipeline_status,
]


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


class ChatResponse(BaseModel):
    reply: str
    tools_used: list[str]


@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(require_api_token)])
async def chat(req: ChatRequest):
    """One chat turn: full message history in, grounded answer out."""
    if not req.messages or req.messages[-1].role != "user":
        raise HTTPException(status_code=400, detail="Last message must be from the user")

    contents = [
        Content(
            role="user" if m.role == "user" else "model",
            parts=[Part(text=m.content[:8000])],
        )
        for m in req.messages[-20:]
    ]

    client = genai.Client(api_key=config.llm.google_api_key)
    try:
        response = await client.aio.models.generate_content(
            model=config.llm.model,
            contents=contents,
            config=GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT.format(today=datetime.now(UTC).date().isoformat()),
                tools=TOOLS,
            ),
        )
    except Exception as e:
        logger.error(f"Chat generation failed: {e}")
        raise HTTPException(status_code=502, detail="LLM request failed") from e

    tools_used = []
    for content in response.automatic_function_calling_history or []:
        for part in content.parts or []:
            if getattr(part, "function_call", None):
                tools_used.append(part.function_call.name)

    return ChatResponse(reply=response.text or "(no answer)", tools_used=tools_used)
