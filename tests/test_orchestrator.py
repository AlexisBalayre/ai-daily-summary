"""Tests for orchestrator module."""

import os
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
