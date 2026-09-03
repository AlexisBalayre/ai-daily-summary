# Good and Bad Tests

Examples use this repo's house style: pytest + pytest-asyncio (`asyncio_mode = "auto"`), `unittest.mock`, the SQLite `session` fixture from `tests/conftest.py`.

## Good Tests

**Integration-style**: Test through real interfaces, not mocks of internal parts.

```python
# GOOD: Tests observable behavior through the extractor's public interface
async def test_rss_extractor_falls_back_to_summary_when_fetch_fails(rss_source, sample_feed):
    extractor = RSSExtractor()

    with patch("ai_daily.etl.extractors.rss.feedparser.parse", return_value=sample_feed):
        with patch("ai_daily.etl.extractors.rss.fetch_url", return_value=None):
            result = await extractor.extract(rss_source)

    assert result[0].content == "Summary of article one"
```

Characteristics:

- Tests behavior users/callers care about
- Uses public API only (`extract()` in, `list[RawContent]` out)
- Survives internal refactors
- Describes WHAT, not HOW
- One logical assertion per test

## Bad Tests

**Implementation-detail tests**: Coupled to internal structure.

```python
# BAD: Tests implementation details
async def test_extract_calls_fetch_url_for_each_entry(rss_source, sample_feed):
    with patch("ai_daily.etl.extractors.rss.feedparser.parse", return_value=sample_feed):
        with patch("ai_daily.etl.extractors.rss.fetch_url") as mock_fetch:
            await RSSExtractor().extract(rss_source)

    assert mock_fetch.call_count == 2
    mock_fetch.assert_any_call("https://example.com/article-1")
```

Red flags:

- Mocking internal collaborators
- Testing private methods (`_parse_entry`, `_create_fallback_summary`)
- Asserting on call counts/order
- Test breaks when refactoring without behavior change
- Test name describes HOW not WHAT
- Verifying through external means instead of interface

```python
# BAD: Bypasses interface to verify
def test_add_source_inserts_row(session):
    add_source(session, name="Tech News", type="rss", config={"url": "https://example.com/feed"})
    row = session.execute(text("SELECT * FROM sources WHERE name = 'Tech News'")).first()
    assert row is not None


# GOOD: Verifies through interface
def test_added_source_is_listed(session):
    source = add_source(
        session, name="Tech News", type="rss", config={"url": "https://example.com/feed"}
    )
    assert source.id in [s.id for s in list_sources(session)]
```

**Tautological tests**: Expected value restates the implementation, so the test passes by construction.

```python
# BAD: Expected value is recomputed the way the code computes it
def test_content_hash_is_md5_of_title_and_content_prefix():
    expected = hashlib.md5(f"{title}{content[:200]}".encode()).hexdigest()
    assert compute_content_hash(title, content) == expected


# GOOD: Expected value is an independent, known literal
def test_content_hash_is_stable_for_known_input():
    assert compute_content_hash("Hello", "World") == "68e109f0f40ca72a15e05cc22786f8e6"


# BAD: a test that never disagrees with the code
async def test_llm_enrich_returns_whatever_the_model_said():
    with patch("ai_daily.etl.enrichment.genai") as mock_genai:
        mock_genai.Client.return_value.aio.models.generate_content = AsyncMock(
            return_value=response
        )
        result = await processor.llm_enrich("t", "c")
    assert result == json.loads(response.text)


# GOOD: asserts a contract the parser must uphold on a hostile input
async def test_llm_enrich_rejects_a_response_with_no_json_object():
    response = MagicMock(text="Sure! Here is the analysis: category=ai")
    with patch("ai_daily.etl.enrichment.genai") as mock_genai:
        mock_genai.Client.return_value.aio.models.generate_content = AsyncMock(
            return_value=response
        )
        with pytest.raises(ValueError, match="Could not parse LLM response"):
            await processor.llm_enrich("t", "c")
```
