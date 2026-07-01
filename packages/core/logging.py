"""Shared logging configuration.

A single ``configure_logging`` entry point so every package logs consistently.
Kept on the standard library for M0; a structured-logging backend can be swapped
in later behind this same interface without changing call sites.
"""

from __future__ import annotations

import logging

from core.config import get_settings

_LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_configured = False


def configure_logging(level: str | None = None) -> None:
    """Configure root logging once. Idempotent across calls."""
    global _configured
    resolved = level or get_settings().log_level
    logging.basicConfig(level=resolved, format=_LOG_FORMAT)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger, ensuring logging is configured first."""
    if not _configured:
        configure_logging()
    return logging.getLogger(name)
