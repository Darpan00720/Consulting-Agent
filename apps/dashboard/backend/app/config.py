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

# Claude API. ANTHROPIC_API_KEY is resolved by the SDK itself (env var or
# `ant auth login` profile) — we never read the key directly.
MODEL = os.environ.get("STRATAGENT_MODEL", "claude-opus-4-8")
MAX_TOKENS = int(os.environ.get("STRATAGENT_MAX_TOKENS", "16000"))
REPORT_MAX_TOKENS = int(os.environ.get("STRATAGENT_REPORT_MAX_TOKENS", "32000"))

# Models a user may pick per engagement, cheapest→best. The tier label and
# rough per-case cost help users iterate cheaply (Haiku) and finalize on Opus.
MODEL_CHOICES = [
    {"id": "claude-haiku-4-5", "label": "Haiku 4.5 — cheapest, for bulk iteration", "tier": "cheap"},
    {"id": "claude-sonnet-5", "label": "Sonnet 5 — balanced, near-Opus quality", "tier": "balanced"},
    {"id": "claude-opus-4-8", "label": "Opus 4.8 — best, for final runs", "tier": "best"},
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

# Whether the server itself has Claude credentials. Users without their own
# key fall back to this (subject to the daily quota); BYOK users are exempt
# from the quota because the spend is theirs.
SERVER_HAS_KEY = bool(
    os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
)

# Per-user daily engagement quota (public-product rate limiting).
DAILY_ENGAGEMENT_QUOTA = int(os.environ.get("STRATAGENT_DAILY_QUOTA", "5"))

# CORS origins for the frontend, comma-separated.
CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get("STRATAGENT_CORS_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]
