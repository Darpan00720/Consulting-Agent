"""Application configuration, sourced from the environment / .env file.

Uses ``pydantic-settings`` so configuration shares the same validation and
type-safety guarantees as the data models, and is ready for FastAPI integration
in a later milestone.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Process-wide settings, read from STRATAGENT_-prefixed env vars."""

    model_config = SettingsConfigDict(
        env_prefix="STRATAGENT_",
        env_file=".env",
        extra="ignore",
    )

    environment: str = "development"
    log_level: str = "INFO"


def get_settings() -> Settings:
    """Return freshly-loaded settings."""
    return Settings()
