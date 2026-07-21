"""Centralized platform configuration (requirement 2).

Immutable after construction (a frozen dataclass — literally cannot be
mutated post-startup). Composes, rather than duplicates, settings that
already exist in ``app.config`` (e.g. Ollama) to avoid a second source of
truth drifting from the first; owns the genuinely NEW settings this phase
introduces (tool allow-lists, memory cache TTL, feature flags).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path


def _env(mapping: Mapping[str, str], name: str, default: str) -> str:
    return mapping.get(name) or default


def _env_bool(mapping: Mapping[str, str], name: str, default: bool) -> bool:
    raw = mapping.get(name)
    if not raw:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_float(mapping: Mapping[str, str], name: str, default: float) -> float:
    raw = mapping.get(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_tuple(
    mapping: Mapping[str, str], name: str, default: tuple[str, ...]
) -> tuple[str, ...]:
    raw = mapping.get(name)
    if not raw:
        return default
    return tuple(s.strip() for s in raw.split(",") if s.strip())


@dataclass(frozen=True)
class PlatformConfig:
    """Every platform-level setting, in one immutable object.

    ``ollama_enabled``/``ollama_placement`` are COMPOSED from ``app.config``
    (already the real, live source of truth for those — ADR-012/013's
    Provider Router) rather than re-parsed from the environment a second
    time, so the two can never drift.
    """

    environment: str  # "development" | "production" | "test"

    # Composed from app.config (Provider Router settings, unchanged source)
    ollama_enabled: bool
    ollama_placement: str

    # New in W6: Tool Platform configuration (requirement 2)
    local_shell_allowed_commands: tuple[str, ...]
    obsidian_vault_dir: Path

    # New in W6: Memory Platform configuration
    memory_cache_ttl_s: float

    # New in W6: feature flags (declarative, requirement 2)
    feature_flags: Mapping[str, bool] = field(default_factory=dict)

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        overrides: Mapping[str, object] | None = None,
    ) -> PlatformConfig:
        """Build config from environment variables + defaults (requirement 2).
        ``env`` defaults to ``os.environ`` (injectable for tests — never reads
        the real process environment implicitly in a test context unless the
        caller passes it explicitly)."""
        raw = dict(env) if env is not None else dict(os.environ)

        # Compose the Provider Router's real settings rather than re-parse —
        # avoids a second, potentially-drifting source of truth.
        from app import config as app_config

        cfg = cls(
            environment=_env(raw, "STRATAGENT_ENV", "development"),
            ollama_enabled=app_config.OLLAMA_ENABLED,
            ollama_placement=app_config.OLLAMA_PLACEMENT,
            local_shell_allowed_commands=_env_tuple(
                raw, "STRATAGENT_SHELL_ALLOWLIST", ()
            ),
            obsidian_vault_dir=Path(
                _env(raw, "STRATAGENT_VAULT_DIR", "knowledge-vault")
            ),
            memory_cache_ttl_s=_env_float(raw, "STRATAGENT_MEMORY_CACHE_TTL_S", 60.0),
            feature_flags={},
        )
        if overrides:
            from dataclasses import replace

            cfg = replace(cfg, **overrides)
        return cfg

    def feature_enabled(self, name: str, default: bool = False) -> bool:
        return self.feature_flags.get(name, default)
