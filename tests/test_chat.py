"""Tests for the chat endpoint and its tool functions (no Gemini calls)."""

from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from ai_daily.api import chat as chat_module
from ai_daily.api.chat import TOOLS, get_leaderboard, list_leaderboards, pipeline_status
from ai_daily.api.server import app
from ai_daily.config import config

client = TestClient(app)

USER_TURN = {"messages": [{"role": "user", "content": "What happened today?"}]}


def _llm_response(text: str, tool_names: list[str] | None = None) -> SimpleNamespace:
    """Shape of google-genai's GenerateContentResponse that the route reads."""
    history = [
        SimpleNamespace(parts=[SimpleNamespace(function_call=SimpleNamespace(name=name))])
        for name in (tool_names or [])
    ]
    history.append(SimpleNamespace(parts=[SimpleNamespace(function_call=None, text="x")]))
    return SimpleNamespace(text=text, automatic_function_calling_history=history)


@pytest.fixture
def genai_client(monkeypatch):
    """Patch the Gemini client factory; returns the AsyncMock for generate_content."""
    monkeypatch.setattr(config, "api_token", "")
    generate = AsyncMock(return_value=_llm_response("Nothing much."))
    fake_client = MagicMock()
    fake_client.aio.models.generate_content = generate
    with patch.object(chat_module.genai, "Client", return_value=fake_client):
        yield generate


def test_chat_returns_model_text_and_tools_used(genai_client):
    genai_client.return_value = _llm_response(
        "Two releases today.", ["latest_releases", "search_articles"]
    )

    response = client.post("/api/v1/chat", json=USER_TURN)

    assert response.status_code == 200
    assert response.json() == {
        "reply": "Two releases today.",
        "tools_used": ["latest_releases", "search_articles"],
    }


def test_chat_passes_tool_registry_and_maps_roles(genai_client):
    body = {
        "messages": [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
            {"role": "user", "content": "releases?"},
        ]
    }

    assert client.post("/api/v1/chat", json=body).status_code == 200

    kwargs = genai_client.call_args.kwargs
    assert kwargs["config"].tools == TOOLS
    assert [c.role for c in kwargs["contents"]] == ["user", "model", "user"]
    assert datetime.now(UTC).date().isoformat() in kwargs["config"].system_instruction


def test_chat_uses_placeholder_when_model_returns_no_text(genai_client):
    genai_client.return_value = _llm_response("")
    assert client.post("/api/v1/chat", json=USER_TURN).json()["reply"] == "(no answer)"


def test_chat_rejects_history_not_ending_with_user(genai_client):
    body = {"messages": [{"role": "assistant", "content": "hello"}]}
    assert client.post("/api/v1/chat", json=body).status_code == 400
    assert client.post("/api/v1/chat", json={"messages": []}).status_code == 400
    genai_client.assert_not_called()


def test_chat_returns_502_when_llm_fails(genai_client):
    genai_client.side_effect = RuntimeError("quota")
    response = client.post("/api/v1/chat", json=USER_TURN)
    assert response.status_code == 502
    assert response.json()["detail"] == "LLM request failed"


def test_chat_requires_bearer_token_when_configured(genai_client, monkeypatch):
    monkeypatch.setattr(config, "api_token", "s3cret")

    assert client.post("/api/v1/chat", json=USER_TURN).status_code == 401
    ok = client.post("/api/v1/chat", json=USER_TURN, headers={"Authorization": "Bearer s3cret"})
    assert ok.status_code == 200


@pytest.fixture
def db_session():
    """Replace get_session in the chat module with a context manager over a MagicMock."""
    session = MagicMock()

    @contextmanager
    def fake_get_session():
        yield session

    with patch.object(chat_module, "get_session", fake_get_session):
        yield session


def test_get_leaderboard_reports_missing_snapshot(db_session):
    db_session.execute.return_value.scalar_one_or_none.return_value = None
    assert get_leaderboard("arena-text") == {"board": "arena-text", "error": "no snapshot"}


def test_get_leaderboard_returns_top_rows(db_session):
    rows = [{"name": f"m{i}", "rank": i + 1} for i in range(10)]
    snap = SimpleNamespace(captured_at=datetime(2026, 9, 3, tzinfo=UTC), row_count=10, rows=rows)
    db_session.execute.return_value.scalar_one_or_none.return_value = snap

    result = get_leaderboard("arena-text", top_n=3)

    assert result["row_count"] == 10
    assert result["captured_at"] == "2026-09-03T00:00:00+00:00"
    assert [r["name"] for r in result["top"]] == ["m0", "m1", "m2"]


def test_list_leaderboards_covers_every_board(db_session):
    from ai_daily.etl.leaderboards import BOARDS

    db_session.execute.return_value.scalar_one_or_none.return_value = None
    result = list_leaderboards()
    assert [b["board"] for b in result] == [b["key"] for b in BOARDS]
    assert all(b["row_count"] == 0 and b["top"] == [] for b in result)


def test_pipeline_status_lists_recent_runs(db_session):
    run = SimpleNamespace(
        job_name="etl", status="success", started_at=datetime(2026, 9, 3, 7, tzinfo=UTC)
    )
    db_session.execute.return_value.scalars.return_value.all.return_value = [run]

    assert pipeline_status() == {
        "recent_jobs": [
            {"name": "etl", "status": "success", "started_at": "2026-09-03T07:00:00+00:00"}
        ]
    }
