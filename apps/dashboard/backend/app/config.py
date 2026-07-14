"""Dashboard configuration — all knobs come from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

# Repo root: apps/dashboard/backend/app/config.py -> four parents up.
REPO_ROOT = Path(__file__).resolve().parents[4]

AGENTS_DIR = Path(
    os.environ.get(
        "STRATAGENT_AGENTS_DIR",
        REPO_ROOT / "plugins" / "ruflo-stratagent" / "agents",
    )
)
VAULT_FRAMEWORKS_DIR = Path(
    os.environ.get(
        "STRATAGENT_VAULT_DIR",
        REPO_ROOT / "knowledge-vault" / "frameworks",
    )
)

DB_PATH = Path(os.environ.get("STRATAGENT_DB", Path(__file__).resolve().parents[1] / "dashboard.db"))

# Groq API — free tier, OpenAI-compatible. Key comes from GROQ_API_KEY env var.
MODEL = os.environ.get("STRATAGENT_MODEL", "llama-3.3-70b-versatile")
MAX_TOKENS = int(os.environ.get("STRATAGENT_MAX_TOKENS", "8000"))
REPORT_MAX_TOKENS = int(os.environ.get("STRATAGENT_REPORT_MAX_TOKENS", "16000"))

# Models available on Groq's free tier (no cost, no card required).
MODEL_CHOICES = [
    {"id": "llama-3.3-70b-versatile", "label": "Llama 3.3 70B — best free quality", "tier": "balanced"},
    {"id": "llama-3.1-8b-instant", "label": "Llama 3.1 8B Instant — fastest", "tier": "cheap"},
    {"id": "moonshotai/kimi-k2-instruct", "label": "Kimi K2 — strong reasoning", "tier": "best"},
]
_ALLOWED_MODELS = {m["id"] for m in MODEL_CHOICES}


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

# Whether the server has a Groq API key. All users share this key
# (rate-limited per client-id by DAILY_ENGAGEMENT_QUOTA).
SERVER_HAS_KEY = bool(os.environ.get("GROQ_API_KEY"))

# Per-user daily engagement quota (public-product rate limiting).
DAILY_ENGAGEMENT_QUOTA = int(os.environ.get("STRATAGENT_DAILY_QUOTA", "5"))

# CORS origins for the frontend, comma-separated.
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get("STRATAGENT_CORS_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]
