"""Tests for ETL pipeline components."""

from ai_daily.etl.transformers import compute_content_hash
from ai_daily.etl.types import RawContent

# Import simplified SQLite-compatible models from conftest
from tests.conftest import SqliteArticle, SqliteSource


def test_compute_content_hash():
    """Test content hash computation."""
    hash1 = compute_content_hash("Title", "Content here")
    hash2 = compute_content_hash("Title", "Content here")
    hash3 = compute_content_hash("Different", "Content here")

    assert hash1 == hash2
    assert hash1 != hash3
    assert len(hash1) == 32  # MD5 hex length


def test_raw_content_creation():
    """Test RawContent dataclass."""
    content = RawContent(
        external_id="test-123",
        title="Test Article",
        content="This is test content",
        url="https://example.com",
    )

    assert content.external_id == "test-123"
    assert content.title == "Test Article"
    assert content.metadata == {}


def test_source_model(session):
    """Test Source model creation with SQLite-compatible model."""
    source = SqliteSource(
        type="newsletter",
        name="Test Newsletter",
        enabled=True,
    )
    source.set_config({"whitelist": ["test@example.com"]})
    session.add(source)
    session.commit()

    assert source.id is not None
    assert source.type == "newsletter"
    assert source.get_config()["whitelist"] == ["test@example.com"]


def test_article_model(session):
    """Test Article model creation with SQLite-compatible model."""
    source = SqliteSource(type="newsletter", name="Test")
    session.add(source)
    session.commit()

    article = SqliteArticle(
        source_id=source.id,
        external_id="article-1",
        title="Test Article",
        content="Test content",
        topic="AI Research and Advances",
        content_hash=compute_content_hash("Test Article", "Test content"),
    )
    session.add(article)
    session.commit()

    assert article.id is not None
    assert article.source_id == source.id
