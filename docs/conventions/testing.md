# Testing

**Genre contract:** obligations only.

## Principles

- Test behaviour through public interfaces, not implementation details; a refactor that keeps behaviour must not break tests. Given input articles, assert the newsletter HTML contains the enriched summary; given an LLM failure, assert the visible fallback is recorded.
- Mock only at system boundaries (LLMs, embeddings, Gmail, the network, the clock), never the module under test or its internal collaborators.
- One reason to fail per test; name tests by the behaviour they pin down.
- A bug fix lands with a regression test that fails without the fix.
- Cover the failure and degradation paths (empty response, JSON parse error, zero recipients): these are where regressions hurt most in this codebase.

## Framework and commands

pytest + pytest-asyncio. `asyncio_mode = "auto"` is set in `pyproject.toml`, so `async def test_*` functions run without a per-test marker.

- All: `uv run pytest` (also `TEST_CMD`, run by `scripts/pre-commit`)
- One file: `uv run pytest tests/test_enrichment.py -v`
- One test: `uv run pytest tests/test_enrichment.py::TestEnrichmentProcessor::test_x -v`

## Layout

- Tests live under `tests/`, files named `test_*.py`, test functions `test_*`.
- Shared fixtures go in `tests/conftest.py`. DB tests use its SQLite-backed session fixture; reuse it rather than standing up Postgres.

## Setup and mocks

- **Never call real LLMs, embeddings, Gmail, or the network in a unit test.** Mock them with `unittest.mock` (the suite does not use `pytest-mock`):
  ```python
  from unittest.mock import AsyncMock, MagicMock, patch


  async def test_generate_embedding_uses_embedder():
      with patch("ai_daily.etl.enrichment.Embedder") as MockEmbedder:
          MockEmbedder.return_value.embed = AsyncMock(return_value=[0.1] * 768)
          processor = EnrichmentProcessor()
          result = await processor.generate_embedding("some article text")
      assert len(result) == 768
  ```
  Use `AsyncMock` for `async def` collaborators and `MagicMock(spec=Source)` for ORM rows the code only reads. `@patch("ai_daily.cli.get_session")` as a decorator is fine for CLI tests.
- Patch at the point of use (`ai_daily.<module>.<name>`), not at the definition site.
- For environment or config values use pytest's `monkeypatch` fixture (`monkeypatch.setenv("GOOGLE_API_KEY", "test")`, `monkeypatch.setattr(config.llm, "model", "x")`) so the change is undone at test end.
- Deterministic time: inject or patch the clock rather than asserting on wall-clock `now()`.
