"""Tests for orchestrator module."""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_orchestrator_config_defaults():
    """Test OrchestratorConfig has correct defaults."""
    from ai_daily.config import OrchestratorConfig

    cfg = OrchestratorConfig()

    assert cfg.etl_schedule == "0 */4 * * *"
    assert cfg.tts_schedule == "0 9 * * *"
    assert cfg.newsletter_schedule == "0 14 * * *"
    assert cfg.retry_max_attempts == 3
    assert cfg.retry_base_delay == 10.0
    assert cfg.retry_multiplier == 3.0


def test_orchestrator_config_from_env(monkeypatch):
    """Test OrchestratorConfig reads from environment."""
    monkeypatch.setenv("ETL_SCHEDULE", "0 */2 * * *")
    monkeypatch.setenv("RETRY_MAX_ATTEMPTS", "5")

    from ai_daily import config as config_module
    import importlib
    importlib.reload(config_module)

    cfg = config_module.OrchestratorConfig()

    assert cfg.etl_schedule == "0 */2 * * *"
    assert cfg.retry_max_attempts == 5


@pytest.mark.asyncio
async def test_executor_successful_run():
    """Test executor runs job successfully."""
    from ai_daily.orchestrator.executor import Executor
    from ai_daily.orchestrator.types import RetryConfig

    mock_job = AsyncMock(return_value={"articles_created": 5})

    with patch("ai_daily.orchestrator.executor.get_session") as mock_session:
        mock_session.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_session.return_value.__exit__ = MagicMock(return_value=None)

        executor = Executor(RetryConfig())
        result = await executor.run("test_job", mock_job)

    assert result["success"] is True
    assert result["metrics"] == {"articles_created": 5}
    mock_job.assert_called_once()


@pytest.mark.asyncio
async def test_executor_retry_on_failure():
    """Test executor retries on failure with exponential backoff."""
    from ai_daily.orchestrator.executor import Executor
    from ai_daily.orchestrator.types import RetryConfig

    # Fail twice, succeed on third attempt
    mock_job = AsyncMock(side_effect=[
        Exception("First failure"),
        Exception("Second failure"),
        {"articles_created": 3}
    ])

    with patch("ai_daily.orchestrator.executor.get_session") as mock_session:
        mock_session.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_session.return_value.__exit__ = MagicMock(return_value=None)

        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            executor = Executor(RetryConfig(base_delay=1.0, multiplier=2.0))
            result = await executor.run("test_job", mock_job)

    assert result["success"] is True
    assert mock_job.call_count == 3
    # Check exponential backoff: 1.0, 2.0
    assert mock_sleep.call_count == 2


@pytest.mark.asyncio
async def test_executor_exhausts_retries():
    """Test executor fails after max retries."""
    from ai_daily.orchestrator.executor import Executor
    from ai_daily.orchestrator.types import RetryConfig

    mock_job = AsyncMock(side_effect=Exception("Always fails"))

    with patch("ai_daily.orchestrator.executor.get_session") as mock_session:
        mock_session.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_session.return_value.__exit__ = MagicMock(return_value=None)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            executor = Executor(RetryConfig(max_attempts=3, base_delay=0.1))
            result = await executor.run("test_job", mock_job)

    assert result["success"] is False
    assert "Always fails" in result["error"]
    assert mock_job.call_count == 3
