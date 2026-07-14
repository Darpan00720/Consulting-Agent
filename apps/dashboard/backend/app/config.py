"""Dashboard configuration — all knobs come from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

def _default_agents_dir() -> Path:
    try:
        return Path(__file__).resolve().parents[4] / "plugins" / "ruflo-stratagent" / "agents"
    except IndexError:
        return Path("/agents")


def _default_vault_dir() -> Path:
    try:
        return Path(__file__).resolve().parents[4] / "knowledge-vault" / "frameworks"
    except IndexError:
        return Path("/vault/frameworks")


AGENTS_DIR = Path(os.environ.get("STRATAGENT_AGENTS_DIR") or str(_default_agents_dir()))
VAULT_FRAMEWORKS_DIR = Path(os.environ.get("STRATAGENT_VAULT_DIR") or str(_default_vault_dir()))

DB_PATH = Path(os.environ.get("STRATAGENT_DB", Path(__file__).resolve().parents[1] / "dashboard.db"))

# LLM access is a multi-provider failover chain (see pipeline/providers.py):
# Gemini 2.5 Flash → OpenRouter free → Groq. Providers join the chain when
# their key is present: GEMINI_API_KEY, OPENROUTER_API_KEY, GROQ_API_KEY.
# Per-provider model overrides: GEMINI_MODEL, OPENROUTER_MODEL, GROQ_MODEL.
# BYOK premium path: a user-supplied Anthropic key runs the whole engagement
# on STRATAGENT_BYOK_MODEL (default claude-opus-4-8), bypassing the free chain
# and the daily quota. The key is per-request only — never stored or logged.
MODEL = "auto"
MAX_TOKENS = int(os.environ.get("STRATAGENT_MAX_TOKENS", "4096"))
REPORT_MAX_TOKENS = int(os.environ.get("STRATAGENT_REPORT_MAX_TOKENS", "8192"))

# The user-facing "model" choice is the chain itself — providers and models
# are a server concern. Legacy Groq ids stay accepted for old clients.
MODEL_CHOICES = [
    {
        "id": "auto",
        "label": "Auto — Gemini 2.5 Flash with automatic fallback (OpenRouter, Groq)",
        "tier": "auto",
    },
]
_LEGACY_MODELS = {
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "meta-llama/llama-4-scout-17b-16e-instruct",
}
_ALLOWED_MODELS = {m["id"] for m in MODEL_CHOICES} | _LEGACY_MODELS


def is_allowed_model(model: str) -> bool:
    return model in _ALLOWED_MODELS

# Governance rework loop (ADR-006): if the reviewer returns needs_rework, the
# implicated analysts are re-dispatched to reconcile the flagged contradictions,
# then the reviewer runs again. This caps how many reconciliation passes run
# before the report-writer falls back to an honest interim status report.
MAX_REWORK = int(os.environ.get("STRATAGENT_MAX_REWORK", "1"))

# Mock mode: run the pipeline with canned outputs instead of calling the API.
# Useful for demos, local frontend work, and tests.
MOCK_MODE = os.environ.get("STRATAGENT_MOCK", "") == "1"

# Whether the server has at least one provider API key. All users share the
# server keys (rate-limited per client-id by DAILY_ENGAGEMENT_QUOTA).
SERVER_HAS_KEY = bool(
    os.environ.get("GEMINI_API_KEY")
    or os.environ.get("GOOGLE_API_KEY")
    or os.environ.get("OPENROUTER_API_KEY")
    or os.environ.get("GROQ_API_KEY")
)

# Per-user daily engagement quota (public-product rate limiting).
DAILY_ENGAGEMENT_QUOTA = int(os.environ.get("STRATAGENT_DAILY_QUOTA", "5"))

# CORS origins for the frontend, comma-separated.
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get("STRATAGENT_CORS_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]
