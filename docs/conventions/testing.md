# Testing Conventions (`tests/`)

pytest + pytest-asyncio. `asyncio_mode = "auto"` is set in `pyproject.toml`, so `async def test_*`
functions run without a per-test marker.

## Layout & naming

- Tests live under `tests/`, files named `test_*.py`, test functions `test_*`.
- Shared fixtures go in `tests/conftest.py`. The suite uses a SQLite-backed session fixture for DB
  tests — reuse it rather than standing up Postgres.

## Mock external services

- **Never call real LLMs, embeddings, Gmail, or the network in a unit test.** Mock them:
  ```python
  async def test_something(mocker):
      mocker.patch("ai_daily.etl.enrichment.embed_text", return_value=[0.1] * 768)
      ...
  ```
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
