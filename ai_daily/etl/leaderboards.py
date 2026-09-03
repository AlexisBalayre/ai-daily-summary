"""Leaderboard watcher: capture external model leaderboards and diff snapshots.

Three fetch strategies, chosen per board:
- "rsc": Next.js server-rendered pages (Artificial Analysis, arena.ai) embed
  their data in React Server Component flight chunks; parsed with no browser.
- "hf-api": Hugging Face leaderboard space exposes a JSON API.
- "browser": Coval renders client-side with no static endpoint, so a headless
  Chromium (playwright) captures the JSON its frontend fetches. Skipped
  gracefully when playwright isn't installed.
"""

import hashlib
import json
import logging
import re
from typing import Any

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_daily.db import LeaderboardSnapshot

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# kind: "rsc" = data present in the server-rendered flight payload;
# "browser" = data fetched client-side, needs headless Chromium;
# "hf-api" = plain JSON API.
BOARDS: list[dict[str, str]] = [
    {
        "key": "aa-speech-to-speech",
        "kind": "browser",
        "url": "https://artificialanalysis.ai/speech-to-speech",
    },
    {
        "key": "aa-stt-streaming",
        "kind": "browser",
        "url": "https://artificialanalysis.ai/speech-to-text/streaming",
    },
    {
        "key": "aa-tts-models",
        "kind": "browser",
        "url": "https://artificialanalysis.ai/text-to-speech/models",
    },
    {"key": "arena-text", "kind": "rsc", "url": "https://arena.ai/leaderboard/text"},
    {"key": "arena-agent", "kind": "browser", "url": "https://arena.ai/leaderboard/agent"},
    {
        "key": "hf-open-llm",
        "kind": "hf-api",
        "url": "https://open-llm-leaderboard-open-llm-leaderboard.hf.space/api/leaderboard/formatted",
    },
    {"key": "coval-tts", "kind": "browser", "url": "https://benchmarks.coval.ai/tts"},
    {"key": "coval-stt", "kind": "browser", "url": "https://benchmarks.coval.ai/stt"},
]

NAME_KEYS = (
    "publicName",
    "displayName",
    "modelDisplayName",
    "modelKey",
    "name",
    "model_name",
    "model",
    "slug",
)
MAX_ROWS_STORED = 300


# ---------- normalization ----------


def _name_key(items: list[dict]) -> str | None:
    """Key most items share holding a string name, or None."""

    def coverage(key: str) -> float:
        return sum(1 for it in items if isinstance(it.get(key), str) and it[key].strip()) / len(
            items
        )

    for key in NAME_KEYS:
        if coverage(key) >= 0.8:
            return key
    # Fallback: any well-covered string key that looks name-ish.
    for key in items[0]:
        if "name" in key.lower() and coverage(key) >= 0.8:
            return key
    return None


def _numeric_keys(items: list[dict]) -> list[str]:
    """Keys carrying numbers in most items (the board's metrics)."""
    counts: dict[str, int] = {}
    for it in items:
        for k, v in it.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                counts[k] = counts.get(k, 0) + 1
    return [k for k, n in counts.items() if n >= 0.5 * len(items)]


def _normalize(items: list[dict], name_key: str, metric_keys: list[str]) -> list[dict]:
    rows = []
    seen = set()
    for it in items:
        if len(rows) >= MAX_ROWS_STORED:
            break
        name = str(it.get(name_key, "")).strip()
        # Dedupe: some boards (Coval) expose per-run rows, several per model.
        if not name or name in seen:
            continue
        seen.add(name)
        row: dict[str, Any] = {"name": name}
        rank = it.get("rank")
        row["rank"] = rank if isinstance(rank, int) else len(rows) + 1
        metrics = {k: it[k] for k in metric_keys[:8] if isinstance(it.get(k), (int, float))}
        if metrics:
            row["metrics"] = metrics
        rows.append(row)
    return rows


def _candidate_arrays(blob: str) -> list[list[dict]]:
    """All JSON arrays-of-objects embedded in a text blob."""
    decoder = json.JSONDecoder()
    out: list[list[dict]] = []
    consumed_until = -1
    for m in re.finditer(r'\[\{"', blob):
        start = m.start()
        if start < consumed_until:
            continue
        try:
            value, end = decoder.raw_decode(blob, start)
        except ValueError:
            continue
        if isinstance(value, list) and len(value) >= 5 and all(isinstance(x, dict) for x in value):
            out.append(value)
            consumed_until = start + end
    return out


def _best_rows(arrays: list[list[dict]]) -> list[dict]:
    """Pick the most leaderboard-like array: named rows carrying numbers.

    Falls back to a model *roster* (membership only, no metrics) for boards
    like Artificial Analysis that embed their model lists but stream chart
    numbers separately — added/removed models still diff correctly.
    """
    best: list[dict] = []
    for items in arrays:
        name_key = _name_key(items)
        if not name_key:
            continue
        metric_keys = _numeric_keys(items)
        has_rank = sum(1 for it in items if isinstance(it.get("rank"), int)) >= 0.5 * len(items)
        if not metric_keys and not has_rank:
            continue
        rows = _normalize(items, name_key, metric_keys)
        if len(rows) > len(best):
            best = rows
    if best:
        return best

    # Roster fallback: union every plausible model list on the page.
    roster: list[dict] = []
    seen: set = set()
    for items in arrays:
        if not (10 <= len(items) <= 300):
            continue
        keys = set(items[0])
        # AA's site-wide LLM catalog (572 models, `isReasoning` flag) is not a
        # board roster; neither is arena's 786-model catalog (`capabilities`).
        if "isReasoning" in keys or "capabilities" in keys or "@type" in keys:
            continue
        if not keys & {"slug", "url", "creator"}:
            continue
        name_key = _name_key(items)
        if not name_key:
            continue
        for it in items:
            name = str(it.get(name_key, "")).strip()
            if name and name not in seen:
                seen.add(name)
                roster.append({"name": name, "rank": len(roster) + 1})
    return roster[:MAX_ROWS_STORED]


# ---------- fetchers ----------


def fetch_rsc(url: str) -> list[dict]:
    """Rows from a Next.js RSC flight payload (server-rendered page)."""
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', resp.text, re.S)
    blob = ""
    for c in chunks:
        try:
            blob += json.loads(f'"{c}"')
        except ValueError:
            continue
    return _best_rows(_candidate_arrays(blob))


def fetch_hf_api(url: str) -> list[dict]:
    """Rows from the Hugging Face leaderboard space JSON API."""
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        return []
    items = []
    for it in data:
        model = it.get("model") or {}
        flat = {"name": model.get("name") or it.get("id", "")}
        # Benchmark numbers live under evaluations.<bench>.{normalized_score, value}.
        scores = []
        for bench, ev in (it.get("evaluations") or {}).items():
            if not isinstance(ev, dict):
                continue
            score = ev.get("normalized_score", ev.get("value"))
            if isinstance(score, (int, float)) and not isinstance(score, bool):
                flat[bench] = score
                scores.append(score)
        if scores:
            flat["average"] = sum(scores) / len(scores)
        items.append(flat)
    # The API lists models alphabetically; rank by average benchmark score.
    items.sort(key=lambda it: it.get("average", float("-inf")), reverse=True)
    metric_keys = _numeric_keys(items)
    return _normalize(items, "name", metric_keys)


async def fetch_browser(url: str) -> list[dict]:
    """Rows via headless Chromium: capture the JSON the page fetches at runtime."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.warning("playwright not installed; skipping browser board %s", url)
        return []

    payloads: list[Any] = []
    flight_texts: list[str] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(user_agent=USER_AGENT)

        async def on_response(response):
            ctype = response.headers.get("content-type") or ""
            try:
                if "json" in ctype:
                    payloads.append(await response.json())
                # RSC streams (Next.js server components / actions) carry raw
                # JSON inline — Artificial Analysis ships its data this way.
                elif "text/x-component" in ctype:
                    flight_texts.append(await response.text())
            except Exception:
                pass

        page.on("response", on_response)
        # "networkidle" never fires on pages with analytics polling (arena.ai);
        # settle for DOM-ready plus a fixed hydration window.
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(8000)
        html = await page.content()
        await browser.close()

    arrays: list[list[dict]] = []

    def collect(node):
        if isinstance(node, list) and len(node) >= 5 and all(isinstance(x, dict) for x in node):
            arrays.append(node)
        elif isinstance(node, dict):
            for v in node.values():
                collect(v)
        elif isinstance(node, list):
            for v in node:
                collect(v)

    for p in payloads:
        collect(p)

    # Second net: raw RSC stream bodies contain unescaped JSON inline.
    for t in flight_texts:
        arrays.extend(_candidate_arrays(t))

    # Third net: the hydrated page's flight chunks.
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', html, re.S)
    blob = ""
    for c in chunks:
        try:
            blob += json.loads(f'"{c}"')
        except ValueError:
            continue
    arrays.extend(_candidate_arrays(blob))

    return _best_rows(arrays)


# ---------- capture + diff ----------


def _hash_rows(rows: list[dict]) -> str:
    names = json.dumps([r["name"] for r in rows], sort_keys=False)
    return hashlib.sha256(names.encode()).hexdigest()


def _latest_snapshot(session: Session, board: str) -> LeaderboardSnapshot | None:
    stmt = (
        select(LeaderboardSnapshot)
        .where(LeaderboardSnapshot.board == board)
        .order_by(LeaderboardSnapshot.captured_at.desc())
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none()


def _diff(old_rows: list[dict], new_rows: list[dict]) -> dict[str, list]:
    old = {r["name"]: r for r in old_rows}
    new = {r["name"]: r for r in new_rows}
    added = [n for n in new if n not in old]
    removed = [n for n in old if n not in new]
    moves = []
    for n in new:
        if n in old and isinstance(new[n].get("rank"), int) and isinstance(old[n].get("rank"), int):
            delta = old[n]["rank"] - new[n]["rank"]
            if abs(delta) >= 3 or (new[n]["rank"] <= 5 and delta > 0):
                moves.append({"name": n, "from": old[n]["rank"], "to": new[n]["rank"]})
    return {"added": added[:15], "removed": removed[:15], "moves": moves[:15]}


async def capture_all(session: Session) -> dict[str, Any]:
    """Capture every board; store changed snapshots; return per-board changes."""
    changes: dict[str, Any] = {}
    captured = errors = unchanged = 0

    for board in BOARDS:
        key, kind, url = board["key"], board["kind"], board["url"]
        try:
            if kind == "rsc":
                rows = fetch_rsc(url)
            elif kind == "hf-api":
                rows = fetch_hf_api(url)
            else:
                rows = await fetch_browser(url)
                if not rows:
                    # Client-rendered boards occasionally miss their data
                    # window on first load; one retry clears most flakes.
                    rows = await fetch_browser(url)
        except Exception as e:
            logger.error("leaderboard fetch failed for %s: %s", key, e)
            errors += 1
            continue

        if not rows:
            logger.warning("leaderboard %s returned no rows; not storing", key)
            errors += 1
            continue

        content_hash = _hash_rows(rows)
        previous = _latest_snapshot(session, key)
        if previous and previous.content_hash == content_hash:
            unchanged += 1
            continue

        session.add(
            LeaderboardSnapshot(
                board=key, rows=rows, row_count=len(rows), content_hash=content_hash
            )
        )
        captured += 1
        if previous and previous.rows:
            diff = _diff(previous.rows, rows)
            if diff["added"] or diff["removed"] or diff["moves"]:
                changes[key] = {**diff, "url": url}

    session.commit()
    return {
        "captured": captured,
        "unchanged": unchanged,
        "errors": errors,
        "changes": changes,
    }
