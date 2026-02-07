"""Tests for article enrichment fields."""

from datetime import datetime, UTC

import pytest

# Import simplified SQLite-compatible models from conftest
from tests.conftest import SqliteSource, SqliteArticle


class TestEnrichmentFields:
    """Test enrichment fields on Article model."""

    def test_article_has_summary_field(self, session):
        """Test that Article has summary field."""
        source = SqliteSource(type="newsletter", name="Test")
        session.add(source)
        session.commit()

        article = SqliteArticle(
            source_id=source.id,
            title="Test Article",
            content="Test content",
            summary="This is an AI-generated summary of the article.",
        )
        session.add(article)
        session.commit()

        assert article.summary == "This is an AI-generated summary of the article."

    def test_article_has_category_field(self, session):
        """Test that Article has category field."""
        source = SqliteSource(type="newsletter", name="Test")
        session.add(source)
        session.commit()

        article = SqliteArticle(
            source_id=source.id,
            title="Test Article",
            content="Test content",
            category="LLM",
        )
        session.add(article)
        session.commit()

        assert article.category == "LLM"

    def test_article_has_is_ai_related_field(self, session):
        """Test that Article has is_ai_related field."""
        source = SqliteSource(type="newsletter", name="Test")
        session.add(source)
        session.commit()

        article = SqliteArticle(
            source_id=source.id,
            title="Test Article",
            content="Test content",
            is_ai_related=True,
        )
        session.add(article)
        session.commit()

        assert article.is_ai_related is True

    def test_article_has_enriched_at_field(self, session):
        """Test that Article has enriched_at field."""
        source = SqliteSource(type="newsletter", name="Test")
        session.add(source)
        session.commit()

        enriched_time = datetime.now(UTC)
        article = SqliteArticle(
            source_id=source.id,
            title="Test Article",
            content="Test content",
            enriched_at=enriched_time,
        )
        session.add(article)
        session.commit()

        # SQLite stores naive datetimes, so compare without timezone
        assert article.enriched_at is not None
        assert article.enriched_at.replace(tzinfo=UTC) == enriched_time

    def test_article_has_is_duplicate_field(self, session):
        """Test that Article has is_duplicate field with default False."""
        source = SqliteSource(type="newsletter", name="Test")
        session.add(source)
        session.commit()

        article = SqliteArticle(
            source_id=source.id,
            title="Test Article",
            content="Test content",
        )
        session.add(article)
        session.commit()

        # Default should be False
        assert article.is_duplicate is False

        # Can be set to True
        article.is_duplicate = True
        session.commit()
        assert article.is_duplicate is True

    def test_article_has_duplicate_of_id_field(self, session):
        """Test that Article has duplicate_of_id field for self-reference."""
        source = SqliteSource(type="newsletter", name="Test")
        session.add(source)
        session.commit()

        # Create original article
        original = SqliteArticle(
            source_id=source.id,
            title="Original Article",
            content="Original content",
        )
        session.add(original)
        session.commit()

        # Create duplicate that references original
        duplicate = SqliteArticle(
            source_id=source.id,
            title="Duplicate Article",
            content="Same content slightly different",
            is_duplicate=True,
            duplicate_of_id=original.id,
        )
        session.add(duplicate)
        session.commit()

        assert duplicate.is_duplicate is True
        assert duplicate.duplicate_of_id == original.id

    def test_enrichment_fields_nullable(self, session):
        """Test that enrichment fields are nullable (except is_duplicate)."""
        source = SqliteSource(type="newsletter", name="Test")
        session.add(source)
        session.commit()

        # Create article without any enrichment fields set
        article = SqliteArticle(
            source_id=source.id,
            title="Test Article",
            content="Test content",
        )
        session.add(article)
        session.commit()

        assert article.summary is None
        assert article.category is None
        assert article.is_ai_related is None
        assert article.enriched_at is None
        assert article.is_duplicate is False  # has default
        assert article.duplicate_of_id is None
