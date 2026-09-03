"""Tests for RSS CLI commands."""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from ai_daily.cli import main


@pytest.fixture
def runner():
    return CliRunner()


def test_run_rss_in_choices(runner):
    """'rss' should be a valid choice for run command."""
    result = runner.invoke(main, ["run", "--help"])
    assert "rss" in result.output


def test_source_add_rss_in_choices(runner):
    """'rss' should be a valid choice for source add command."""
    result = runner.invoke(main, ["source", "add", "--help"])
    assert "rss" in result.output


def test_source_add_rss_command_exists(runner):
    """source add-rss command should exist."""
    result = runner.invoke(main, ["source", "add-rss", "--help"])
    assert result.exit_code == 0
    assert "NAME" in result.output
    assert "URL" in result.output


@patch("ai_daily.cli.get_session")
def test_source_add_rss_creates_source(mock_get_session, runner):
    """source add-rss should create an RSS source."""
    mock_session = MagicMock()
    mock_get_session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

    # Mock the source to have an ID after add
    def set_id(src):
        src.id = 42

    mock_session.add.side_effect = set_id

    result = runner.invoke(main, ["source", "add-rss", "Test Feed", "https://example.com/feed.xml"])

    assert result.exit_code == 0
    assert "Added RSS source: Test Feed" in result.output

    # Verify source was created with correct config
    added_source = mock_session.add.call_args[0][0]
    assert added_source.type == "rss"
    assert added_source.name == "Test Feed"
    assert added_source.config == {"url": "https://example.com/feed.xml"}
    assert added_source.enabled is True


def test_enrichment_not_in_run_choices(runner):
    """'enrichment' should not be a CLI choice (now merged into ETL)."""
    result = runner.invoke(main, ["run", "--help"])
    assert "enrichment" not in result.output
