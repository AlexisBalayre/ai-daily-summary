"""Tests for the leaderboard watcher: normalisation, hashing, diffing, capture."""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ai_daily.db import LeaderboardSnapshot
from ai_daily.etl import leaderboards
from ai_daily.etl.leaderboards import (
    MAX_ROWS_STORED,
    _best_rows,
    _candidate_arrays,
    _diff,
    _hash_rows,
    _normalize,
    capture_all,
    fetch_browser,
    fetch_hf_api,
)


def _items(names: list[str], **extra) -> list[dict]:
    return [{"name": n, "score": float(i), **extra} for i, n in enumerate(names)]


def test_normalize_dedupes_names_and_assigns_positional_rank():
    items = _items(["a", "b", "a", "c"])
    rows = _normalize(items, "name", ["score"])
    assert [r["name"] for r in rows] == ["a", "b", "c"]
    assert [r["rank"] for r in rows] == [1, 2, 3]
    assert rows[1]["metrics"] == {"score": 1.0}


def test_normalize_keeps_explicit_integer_rank_and_skips_blank_names():
    items = [{"name": "x", "rank": 7}, {"name": "  ", "rank": 1}, {"name": "y", "rank": "2"}]
    rows = _normalize(items, "name", [])
    assert rows == [{"name": "x", "rank": 7}, {"name": "y", "rank": 2}]


def test_normalize_caps_rows_at_max_rows_stored():
    items = _items([f"model-{i}" for i in range(MAX_ROWS_STORED + 50)])
    assert len(_normalize(items, "name", ["score"])) == MAX_ROWS_STORED


def test_normalize_limits_metrics_to_eight_keys():
    item = {"name": "m", **{f"k{i}": i for i in range(12)}}
    rows = _normalize([item], "name", [f"k{i}" for i in range(12)])
    assert len(rows[0]["metrics"]) == 8


def test_hash_is_stable_for_same_names_and_ignores_metrics():
    rows_a = [{"name": "a", "rank": 1, "metrics": {"s": 1}}, {"name": "b", "rank": 2}]
    rows_b = [{"name": "a", "rank": 1, "metrics": {"s": 99}}, {"name": "b", "rank": 5}]
    assert _hash_rows(rows_a) == _hash_rows(rows_b)


def test_hash_changes_with_order_or_names():
    base = _hash_rows([{"name": "a"}, {"name": "b"}])
    assert _hash_rows([{"name": "b"}, {"name": "a"}]) != base
    assert _hash_rows([{"name": "a"}, {"name": "c"}]) != base


def test_diff_reports_added_removed_and_significant_moves():
    old = [{"name": n, "rank": i + 1} for i, n in enumerate(["a", "b", "c", "d", "e", "f", "g"])]
    new = [{"name": n, "rank": i + 1} for i, n in enumerate(["b", "a", "g", "c", "d", "e", "h"])]

    diff = _diff(old, new)

    assert diff["added"] == ["h"]
    assert diff["removed"] == ["f"]
    moves = {m["name"]: (m["from"], m["to"]) for m in diff["moves"]}
    # "b" climbs into the top 5 (1 place), "g" jumps 4 places; "a" only drops one.
    assert moves == {"b": (2, 1), "g": (7, 3)}


def test_candidate_arrays_and_best_rows_pick_named_numeric_table():
    table = [{"model": f"m{i}", "elo": 1000 + i, "rank": i + 1} for i in range(6)]
    noise = [{"id": i} for i in range(6)]
    blob = f"prefix {_dump(noise)} middle {_dump(table)} suffix"

    arrays = _candidate_arrays(blob)
    rows = _best_rows(arrays)

    assert len(arrays) == 2
    assert [r["name"] for r in rows] == [f"m{i}" for i in range(6)]
    assert rows[0]["metrics"]["elo"] == 1000


def _dump(value) -> str:
    import json

    return json.dumps(value, separators=(",", ":"))


def test_fetch_hf_api_ranks_by_average_benchmark_score():
    payload = [
        {"model": {"name": "low"}, "evaluations": {"a": {"normalized_score": 10.0}}},
        {"model": {"name": "high"}, "evaluations": {"a": {"value": 90.0}, "b": {"value": 70.0}}},
        {"id": "no-scores", "evaluations": {}},
    ]
    resp = MagicMock()
    resp.json.return_value = payload
    with patch("ai_daily.etl.leaderboards.requests.get", return_value=resp):
        rows = fetch_hf_api("https://example.test/api")

    assert [r["name"] for r in rows] == ["high", "low", "no-scores"]
    assert rows[0]["metrics"]["average"] == 80.0


async def test_fetch_browser_skips_gracefully_without_playwright(monkeypatch):
    monkeypatch.setitem(sys.modules, "playwright.async_api", None)
    assert await fetch_browser("https://example.test") == []


def _board_setup(monkeypatch, rows: list[dict], previous=None):
    monkeypatch.setattr(
        leaderboards, "BOARDS", [{"key": "b1", "kind": "rsc", "url": "https://x.test"}]
    )
    monkeypatch.setattr(leaderboards, "fetch_rsc", lambda url: rows)
    monkeypatch.setattr(leaderboards, "_latest_snapshot", lambda session, board: previous)


async def test_capture_all_stores_nothing_for_unchanged_board(monkeypatch):
    rows = [{"name": "a", "rank": 1}, {"name": "b", "rank": 2}]
    previous = SimpleNamespace(content_hash=_hash_rows(rows), rows=rows)
    _board_setup(monkeypatch, rows, previous)
    session = MagicMock()

    result = await capture_all(session)

    session.add.assert_not_called()
    session.commit.assert_called_once()
    assert result == {"captured": 0, "unchanged": 1, "errors": 0, "changes": {}}


async def test_capture_all_stores_snapshot_and_reports_changes(monkeypatch):
    old_rows = [{"name": "a", "rank": 1}, {"name": "b", "rank": 2}]
    new_rows = [{"name": "a", "rank": 1}, {"name": "c", "rank": 2}]
    previous = SimpleNamespace(content_hash=_hash_rows(old_rows), rows=old_rows)
    _board_setup(monkeypatch, new_rows, previous)
    session = MagicMock()

    result = await capture_all(session)

    snapshot = session.add.call_args.args[0]
    assert isinstance(snapshot, LeaderboardSnapshot)
    assert snapshot.board == "b1"
    assert snapshot.row_count == 2
    assert snapshot.content_hash == _hash_rows(new_rows)
    assert result["captured"] == 1
    assert result["changes"]["b1"]["added"] == ["c"]
    assert result["changes"]["b1"]["removed"] == ["b"]
    assert result["changes"]["b1"]["url"] == "https://x.test"


async def test_capture_all_first_snapshot_has_no_changes(monkeypatch):
    _board_setup(monkeypatch, [{"name": "a", "rank": 1}], previous=None)
    session = MagicMock()

    result = await capture_all(session)

    assert result["captured"] == 1
    assert result["changes"] == {}


async def test_capture_all_counts_fetch_failures_and_empty_boards(monkeypatch):
    monkeypatch.setattr(
        leaderboards,
        "BOARDS",
        [
            {"key": "boom", "kind": "rsc", "url": "https://boom.test"},
            {"key": "empty", "kind": "hf-api", "url": "https://empty.test"},
        ],
    )

    def explode(url):
        raise RuntimeError("network down")

    monkeypatch.setattr(leaderboards, "fetch_rsc", explode)
    monkeypatch.setattr(leaderboards, "fetch_hf_api", lambda url: [])
    session = MagicMock()

    result = await capture_all(session)

    session.add.assert_not_called()
    assert result["errors"] == 2
    assert result["captured"] == 0
