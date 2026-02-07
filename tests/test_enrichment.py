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


class TestEnrichmentProcessor:
    """Test EnrichmentProcessor class and EnrichmentStats dataclass."""

    def test_enrichment_processor_can_be_imported(self):
        """Test that EnrichmentProcessor can be imported."""
        from ai_daily.etl.enrichment import EnrichmentProcessor
        assert EnrichmentProcessor is not None

    def test_enrichment_processor_batch_size_constant(self):
        """Test that BATCH_SIZE constant is 50."""
        from ai_daily.etl.enrichment import EnrichmentProcessor
        assert EnrichmentProcessor.BATCH_SIZE == 50

    def test_enrichment_processor_similarity_threshold_constant(self):
        """Test that SIMILARITY_THRESHOLD constant is 0.92."""
        from ai_daily.etl.enrichment import EnrichmentProcessor
        assert EnrichmentProcessor.SIMILARITY_THRESHOLD == 0.92

    def test_enrichment_processor_lookback_days_constant(self):
        """Test that LOOKBACK_DAYS constant is 7."""
        from ai_daily.etl.enrichment import EnrichmentProcessor
        assert EnrichmentProcessor.LOOKBACK_DAYS == 7

    def test_enrichment_stats_can_be_imported(self):
        """Test that EnrichmentStats can be imported."""
        from ai_daily.etl.enrichment import EnrichmentStats
        assert EnrichmentStats is not None

    def test_enrichment_stats_default_values(self):
        """Test that EnrichmentStats has correct default values."""
        from ai_daily.etl.enrichment import EnrichmentStats
        stats = EnrichmentStats()
        assert stats.processed == 0
        assert stats.duplicates == 0
        assert stats.ai_related == 0
        assert stats.errors == 0

    def test_enrichment_stats_custom_values(self):
        """Test that EnrichmentStats accepts custom values."""
        from ai_daily.etl.enrichment import EnrichmentStats
        stats = EnrichmentStats(processed=10, duplicates=2, ai_related=8, errors=1)
        assert stats.processed == 10
        assert stats.duplicates == 2
        assert stats.ai_related == 8
        assert stats.errors == 1
