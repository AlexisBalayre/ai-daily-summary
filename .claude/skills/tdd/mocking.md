# When to Mock

Mock at **system boundaries** only. In this repo those are:

- LLM and embedding APIs (Gemini via `google.genai`)
- Gmail API (reading newsletters, sending email) and the OAuth token flow
- GitHub, RSS feeds, crawled sites (`aiohttp` / `feedparser` / `trafilatura`)
- PostgreSQL (prefer the SQLite `session` fixture in `tests/conftest.py` over a mock)
- Time/randomness
- File system (sometimes: templates, `token.json`)

Don't mock:

- Your own classes/modules (`EnrichmentProcessor`, `NewsletterOutput`, the extractors)
- Internal collaborators
- Anything you control

## Tools

The suite uses `unittest.mock`, not `pytest-mock`. Reach for:

- `patch("ai_daily.<module>.<name>")` as a context manager (or decorator for CLI tests), always at the point of use, never at the definition site.
- `AsyncMock` for any `async def` collaborator (`embed`, `generate_content`, `fetch_url`); a plain `MagicMock` returns a non-awaitable and fails with a confusing `TypeError`.
- `MagicMock(spec=Source)` for ORM rows the code only reads; the SQLite fixture when it writes.
- pytest's `monkeypatch` for environment and config (`monkeypatch.setenv`, `monkeypatch.setattr(config.llm, ...)`) so the change is undone at test end.

```python
async def test_enrichment_stores_embedding():
    with patch("ai_daily.etl.enrichment.Embedder") as MockEmbedder:
        MockEmbedder.return_value.embed = AsyncMock(return_value=[0.1] * 768)
        processor = EnrichmentProcessor()
        embedding = await processor.generate_embedding("article text")

    assert len(embedding) == 768
```

## Designing for Mockability

At system boundaries, design interfaces that are easy to mock:

**1. Use dependency injection**

Pass external dependencies in rather than creating them internally:

```python
# Easy to mock: the client crosses the seam as a parameter
async def summarize(article: Article, llm: LLMClient) -> str:
    return await llm.complete(SUMMARY_PROMPT.format(title=article.title, content=article.content))

# Hard to mock: the function builds its own client from config
async def summarize(article: Article) -> str:
    client = genai.Client(api_key=config.llm.google_api_key)
    response = await client.aio.models.generate_content(model=config.llm.model, contents=...)
    return response.text
```

The second shape is what `EnrichmentProcessor` does today (a lazily built `Embedder`, a `genai.Client` inside `llm_enrich`), which is why its tests patch `ai_daily.etl.enrichment.Embedder` and `ai_daily.etl.enrichment.genai` rather than injecting. It works, but every test must know the module's internals to find the patch target.

**2. Prefer SDK-style interfaces over generic fetchers**

Create specific functions for each external operation instead of one generic function with conditional logic:

```python
# GOOD: Each function is independently mockable
class GitHubClient:
    async def trending(self, language: str | None = None) -> list[Repo]: ...
    async def repo(self, full_name: str) -> Repo: ...
    async def readme(self, full_name: str) -> str: ...

# BAD: Mocking requires conditional logic inside the mock
class GitHubClient:
    async def get(self, path: str, params: dict | None = None) -> dict: ...
```

The SDK approach means:

- Each mock returns one specific shape (`AsyncMock(return_value=[Repo(...)])`)
- No conditional logic in test setup (no `side_effect` that branches on the URL)
- Easier to see which endpoints a test exercises
- Type hints per operation instead of `dict`
