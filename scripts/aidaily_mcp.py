# /// script
# requires-python = ">=3.12"
# dependencies = ["mcp>=1.2.0", "httpx>=0.27"]
# ///
"""AI Daily MCP server — exposes the ai-daily platform to MCP clients.

Runs on the host (outside Docker) and adapts the REST API on localhost:8000.
Served over the tailnet via `tailscale serve`, so every device on the
Tailscale network can use it from Claude Code / Desktop / mobile.

Run: uv run --script aidaily_mcp.py
Env: AIDAILY_API (default http://127.0.0.1:8000/api/v1), MCP_PORT (default 8765)
"""

import os
from datetime import date

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

API = os.getenv("AIDAILY_API", "http://127.0.0.1:8000/api/v1").rstrip("/")
PORT = int(os.getenv("MCP_PORT", "8765"))
# The tailnet DNS name `tailscale serve` publishes; requests arrive with this Host.
PUBLIC_HOST = os.getenv("MCP_PUBLIC_HOST", "my-host.tailnet.ts.net")

mcp = FastMCP(
    "ai-daily",
    host="127.0.0.1",
    port=PORT,
    # Stateless: any tailnet device can call without session affinity, and a
    # server restart never strands clients with stale session ids.
    stateless_http=True,
    transport_security=TransportSecuritySettings(
        allowed_hosts=[PUBLIC_HOST, f"{PUBLIC_HOST}:443", f"127.0.0.1:{PORT}", f"localhost:{PORT}"],
        allowed_origins=[f"https://{PUBLIC_HOST}", f"http://127.0.0.1:{PORT}"],
    ),
)
client = httpx.Client(base_url=API, timeout=30)


def _get(path: str, **params) -> object:
    r = client.get(path, params={k: v for k, v in params.items() if v is not None})
    r.raise_for_status()
    return r.json()


def _article_brief(a: dict) -> dict:
    return {
        "id": a.get("id"),
        "title": a.get("title"),
        "url": a.get("url"),
        "summary": a.get("summary"),
        "category": a.get("category"),
        "tags": a.get("tags"),
        "source": a.get("source_name"),
        "ingested_at": a.get("ingested_at"),
    }


# ---------- Read tools ----------


@mcp.tool()
def search_articles(query: str, limit: int = 10) -> list[dict]:
    """Search the article database by keyword (titles + content)."""
    return [_article_brief(a) for a in _get("/search", q=query, limit=min(limit, 50))]


@mcp.tool()
def list_articles(
    limit: int = 20,
    category: str | None = None,
    ai_only: bool = True,
    source_type: str | None = None,
) -> list[dict]:
    """List recent articles, newest first. source_type: rss, newsletter, github, crawler."""
    return [
        _article_brief(a)
        for a in _get(
            "/articles",
            limit=min(limit, 100),
            category=category,
            is_ai_related=True if ai_only else None,
            is_duplicate=False,
            source_type=source_type,
        )
    ]


@mcp.tool()
def get_article(article_id: int) -> dict:
    """Full detail of one article, including its content."""
    return _get(f"/articles/{article_id}")


@mcp.tool()
def search_github_repos(query: str = "", limit: int = 15) -> list[dict]:
    """Search trending GitHub repos ingested by the pipeline (name, description, tags).

    Empty query returns the latest trending repos.
    """
    return [
        {
            "repo": a.get("title"),
            "url": a.get("url"),
            "summary": a.get("summary") or (a.get("content") or "")[:200],
            "tags": a.get("tags"),
            "ingested_at": a.get("ingested_at"),
        }
        for a in _get(
            "/articles",
            q=query or None,
            source_type="github",
            is_duplicate=False,
            limit=min(limit, 100),
        )
    ]


@mcp.tool()
def latest_releases(days: int = 7) -> list[dict]:
    """New AI model releases detected in the last N days (the Release Radar)."""
    return _get("/releases", days=days)


@mcp.tool()
def daily_summary(target_date: str | None = None) -> dict:
    """The LLM-generated daily summary. target_date: YYYY-MM-DD, default today."""
    return _get(f"/summary/{target_date or date.today().isoformat()}")


@mcp.tool()
def pipeline_status() -> dict:
    """Platform health: article/source counts plus the last 10 job runs."""
    return {"status": _get("/status"), "recent_jobs": _get("/jobs", limit=10)}


# ---------- Manage tools ----------


@mcp.tool()
def list_sources() -> list[dict]:
    """All content sources (rss, crawler, newsletter, github) and whether they're enabled."""
    return _get("/sources")


@mcp.tool()
def add_rss_source(name: str, url: str) -> dict:
    """Add and enable a new RSS/Atom feed as a content source."""
    r = client.post("/sources", json={"type": "rss", "name": name, "config": {"url": url}})
    r.raise_for_status()
    return r.json()


@mcp.tool()
def toggle_source(source_id: int) -> dict:
    """Enable/disable a source by id (see list_sources)."""
    r = client.patch(f"/sources/{source_id}/toggle")
    r.raise_for_status()
    return r.json()


@mcp.tool()
def get_whitelist() -> dict:
    """Newsletter sender whitelist (which senders' emails get ingested)."""
    return _get("/whitelist")


@mcp.tool()
def add_to_whitelist(email: str) -> dict:
    """Add a newsletter sender address to the ingestion whitelist."""
    r = client.post("/whitelist", json={"email": email})
    r.raise_for_status()
    return r.json()


@mcp.tool()
def remove_from_whitelist(email: str) -> str:
    """Remove a sender address from the ingestion whitelist."""
    r = client.delete(f"/whitelist/{email}")
    r.raise_for_status()
    return f"removed {email}"


@mcp.tool()
def trigger_job(job_name: str) -> dict:
    """Run a pipeline job now. job_name: etl, newsletter, github, tts, or leaderboards.

    etl ingests + enriches new articles (and sends release alerts);
    newsletter sends the daily email with the audio briefing;
    leaderboards re-captures all model leaderboards and alerts on changes.
    """
    r = client.post(f"/jobs/{job_name}/trigger")
    r.raise_for_status()
    return r.json()


@mcp.tool()
def leaderboards() -> list[dict]:
    """Latest snapshot summary (top models, row count, capture time) for every tracked leaderboard: Artificial Analysis speech boards, arena.ai, HF Open LLM, Coval TTS/STT."""
    return _get("/leaderboards")


@mcp.tool()
def leaderboard(board: str, limit: int = 25) -> dict:
    """Full latest snapshot of one leaderboard. board keys: aa-speech-to-speech, aa-stt-streaming, aa-tts-models, arena-text, arena-agent, hf-open-llm, coval-tts, coval-stt."""
    return _get(f"/leaderboards/{board}", limit=limit)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
