# Testing Conventions (`tests/`)

pytest + pytest-asyncio. `asyncio_mode = "auto"` is set in `pyproject.toml`, so `async def test_*`
functions run without a per-test marker.

## Layout & naming

- Tests live under `tests/`, files named `test_*.py`, test functions `test_*`.
- Shared fixtures go in `tests/conftest.py`. The suite uses a SQLite-backed session fixture for DB
  tests — reuse it rather than standing up Postgres.

## Mock external services

- **Never call real LLMs, embeddings, Gmail, or the network in a unit test.** Mock them with
  `unittest.mock` (the suite does not use `pytest-mock`):
  ```python
  from unittest.mock import AsyncMock, MagicMock, patch

  async def test_generate_embedding_uses_embedder():
      with patch("ai_daily.etl.enrichment.Embedder") as MockEmbedder:
          MockEmbedder.return_value.embed = AsyncMock(return_value=[0.1] * 768)
          processor = EnrichmentProcessor()
          result = await processor.generate_embedding("some article text")
      assert len(result) == 768
  ```
  Use `AsyncMock` for `async def` collaborators and `MagicMock(spec=Source)` for ORM rows the
  code only reads. `@patch("ai_daily.cli.get_session")` as a decorator is fine for CLI tests.
- For environment or config values prefer pytest's `monkeypatch` fixture
  (`monkeypatch.setenv("GOOGLE_API_KEY", "test")`, `monkeypatch.setattr(config.llm, "model", "x")`)
  so the change is undone automatically at test end.
- Patch at the point of use (`ai_daily.<module>.<name>`), not at the definition site.

## What to test

- Test **behaviour and contracts**, not private internals: given input articles, assert the newsletter
  HTML contains the enriched summary; given an LLM failure, assert the visible fallback is recorded.
- Cover the failure/degradation paths (empty response, JSON parse error, zero recipients) — these are
  where regressions hurt most in this codebase.
- Deterministic time: inject/patch the clock rather than asserting on wall-clock `now()`.

## Running

- All: `uv run pytest`
- One file: `uv run pytest tests/test_enrichment.py -v`
- One test: `uv run pytest tests/test_enrichment.py::TestEnrichmentProcessor::test_x -v`
