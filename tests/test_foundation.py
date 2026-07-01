"""M0 foundation smoke tests: settings load and logging configures."""

from __future__ import annotations

from core.config import Settings, get_settings
from core.logging import get_logger


def test_settings_defaults() -> None:
    settings = get_settings()
    assert isinstance(settings, Settings)
    assert settings.environment
    assert settings.log_level


def test_logger_smoke() -> None:
    logger = get_logger("stratagent.test")
    logger.info("logging is configured")
    assert logger.name == "stratagent.test"
