"""Dashboard configuration — all knobs come from environment variables."""

from __future__ import annotations

import os
import secrets
from pathlib import Path


def _env(name: str, default: str) -> str:
    """``os.environ.get`` that treats an EMPTY value as absent.

    docker-compose's ``VAR: ${VAR:-}`` — the standard way to make a variable
    optional — exports an empty STRING when the host hasn't set it. Plain
    ``os.environ.get(name, default)`` then returns "" rather than the default,
    which silently blanks a setting or, for ``int("")``, crashes the process at
    import. Every env read here must go through this.
    """
    return os.environ.get(name) or default


def _default_agents_dir() -> Path:
    try:
        return (
            Path(__file__).resolve().parents[4]
            / "plugins"
            / "ruflo-stratagent"
            / "agents"
        )
    except IndexError:
        return Path("/agents")


def _default_vault_dir() -> Path:
    try:
        return Path(__file__).resolve().parents[4] / "knowledge-vault" / "frameworks"
    except IndexError:
        return Path("/vault/frameworks")


AGENTS_DIR = Path(os.environ.get("STRATAGENT_AGENTS_DIR") or str(_default_agents_dir()))
VAULT_FRAMEWORKS_DIR = Path(
    os.environ.get("STRATAGENT_VAULT_DIR") or str(_default_vault_dir())
)

DB_PATH = Path(
    _env("STRATAGENT_DB", str(Path(__file__).resolve().parents[1] / "dashboard.db"))
)

# LLM access is a multi-provider failover chain (see pipeline/providers.py):
# Gemini → Cerebras → OpenRouter → GitHub Models → Cloudflare Workers AI.
# Providers join the chain when their key is present: GEMINI_API_KEY,
# CEREBRAS_API_KEY, OPENROUTER_API_KEY, GITHUB_MODELS_TOKEN, and
# CLOUDFLARE_ACCOUNT_ID + CLOUDFLARE_API_TOKEN (Cloudflare needs both).
# Per-provider model overrides: GEMINI_MODEL, CEREBRAS_MODEL, OPENROUTER_MODEL,
# GITHUB_MODELS_MODEL, CLOUDFLARE_MODEL.
# BYOK premium path: a user-supplied Anthropic key runs the whole engagement
# on STRATAGENT_BYOK_MODEL (default claude-opus-4-8), bypassing the free chain
# and the daily quota. The key is per-request only — never stored or logged.
MODEL = "auto"
MAX_TOKENS = int(_env("STRATAGENT_MAX_TOKENS", "4096"))
REPORT_MAX_TOKENS = int(_env("STRATAGENT_REPORT_MAX_TOKENS", "8192"))

# Local model via Ollama (pipeline/providers.py, docs/operations/
# Ollama-Local-Runtime.md). Opt-in and additive — the cloud chain is unchanged
# when this is off. A local model is a weak analyst, so the default placement is
# "last" (zero-cost offline fallback); set OLLAMA_PLACEMENT=first for a
# local-first cost saver that falls back to cloud automatically.
#   OLLAMA_ENABLED   — "1" joins Ollama to the chain (default off).
#   OLLAMA_BASE_URL  — OpenAI-compatible endpoint (default http://localhost:11434/v1).
#   OLLAMA_MODEL     — pulled model id (default qwen3:4b).
#   OLLAMA_PLACEMENT — "first" (local-first) or "last" (fallback, default).
OLLAMA_ENABLED = _env("OLLAMA_ENABLED", "") == "1"
OLLAMA_BASE_URL = _env("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = _env("OLLAMA_MODEL", "qwen3:4b")
OLLAMA_PLACEMENT = _env("OLLAMA_PLACEMENT", "last")

# The user-facing "model" choice is the chain itself — providers and models
# are a server concern. Legacy Groq ids stay accepted for old clients.
MODEL_CHOICES = [
    {
        "id": "auto",
        "label": "Auto — best available provider, with automatic fallback",
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
MAX_REWORK = int(_env("STRATAGENT_MAX_REWORK", "1"))

# Mock mode: run the pipeline with canned outputs instead of calling the API.
# Useful for demos, local frontend work, and tests.
MOCK_MODE = _env("STRATAGENT_MOCK", "") == "1"

# Operator ("admin") console. Exposes EVERY client's cases, feedback and failure
# traces, so it is gated on a shared secret from the environment. Unset = the
# routes 404 (not 403): an endpoint that isn't configured shouldn't advertise
# that it exists. This is deliberately not an account system — there is exactly
# one operator, and the product's promise is that users never sign up.
ADMIN_TOKEN = _env("STRATAGENT_ADMIN_TOKEN", "")

# Operational telemetry (packages/telemetry, wired via app/telemetry_bridge.py).
# Separate from the domain event log: this is for OPERATORS (durations, retries,
# failures), is sampled and redacted, and may be dropped without affecting an
# engagement. One JSONL file per engagement under TELEMETRY_DIR.
#   TELEMETRY_ENABLED — kill switch.
#   TELEMETRY_DIR — output root; empty disables writing (NullSink).
#   TELEMETRY_SAMPLE_RATE — 0.0–1.0; 1.0 records everything.
TELEMETRY_ENABLED = _env("STRATAGENT_TELEMETRY", "1") == "1"
TELEMETRY_DIR = _env("STRATAGENT_TELEMETRY_DIR", "") or str(
    DB_PATH.parent / "telemetry"
)
TELEMETRY_SAMPLE_RATE = float(_env("STRATAGENT_TELEMETRY_SAMPLE", "1.0"))

# ADR-014 Phase 1 — app.knowledge (typed framework catalog) integration into
# the framing-phase prompt. Purely additive: an extra reference section
# alongside (never replacing) the existing knowledge-vault index. Default
# off, consistent with ADR-014 §5 "feature-flagged rollout... defaulting to
# off in production until explicitly enabled."
#   KNOWLEDGE_LIBRARY_ENABLED — "1" adds the app.knowledge index to the
#   framing prompt (default off; framing prompt is byte-identical when off).
KNOWLEDGE_LIBRARY_ENABLED = _env("STRATAGENT_KNOWLEDGE_LIBRARY", "") == "1"

# ADR-014 Phase 2 — app.organization (typed 25-role catalog) integration into
# the planning-phase prompt. Purely additive: an extra reference section for
# the planner agent alongside its existing free-text engagement plan. Same
# feature-flagged-off-by-default convention as Phase 1.
#   ORGANIZATION_LAYER_ENABLED — "1" adds the app.organization index to the
#   planning prompt (default off; planning prompt is byte-identical when off).
ORGANIZATION_LAYER_ENABLED = _env("STRATAGENT_ORGANIZATION_LAYER", "") == "1"

# Max engagements running their LLM pipeline at once (server-wide). Requests
# still return 202 immediately; work beyond this waits its turn rather than
# piling unbounded concurrent load onto the single SQLite writer and the shared
# provider quota. Raise it as provider capacity (more keys) grows.
MAX_CONCURRENT_ENGAGEMENTS = int(_env("STRATAGENT_MAX_CONCURRENT", "8"))

# Auto-resume on rate-limit exhaustion. When every provider is rate-limited at
# once, the engine checkpoints completed phases, pauses the engagement, waits
# for the soonest provider to refill, then resumes from where it left off —
# instead of failing and losing the work. These bound that behaviour.
#   MAX_AUTO_RESUMES — give up (mark failed) after this many automatic retries.
#   MIN/MAX_RESUME_DELAY — clamp the wait so it's neither a busy-loop nor a stall.
#   AUTO_RESUME — kill switch (tests set 0 to inspect the paused state directly).
MAX_AUTO_RESUMES = int(_env("STRATAGENT_MAX_AUTO_RESUMES", "6"))
MIN_RESUME_DELAY = float(_env("STRATAGENT_MIN_RESUME_DELAY", "20"))
MAX_RESUME_DELAY = float(_env("STRATAGENT_MAX_RESUME_DELAY", "900"))
AUTO_RESUME = _env("STRATAGENT_AUTO_RESUME", "1") == "1"

# Whether the server has at least one provider API key. All users share the
# server keys (rate-limited per client-id by DAILY_ENGAGEMENT_QUOTA).
# Must list every provider build_chain() can construct, or a server configured
# with only a new provider's key would wrongly report "no free tier".
# Cloudflare needs BOTH an account id (baked into its URL) and a token.
SERVER_HAS_KEY = bool(
    os.environ.get("GEMINI_API_KEY")
    or os.environ.get("GOOGLE_API_KEY")
    or os.environ.get("CEREBRAS_API_KEY")
    or os.environ.get("OPENROUTER_API_KEY")
    or os.environ.get("GITHUB_MODELS_TOKEN")
    or os.environ.get("GITHUB_TOKEN")
    or (
        os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        and os.environ.get("CLOUDFLARE_API_TOKEN")
    )
    # A local Ollama model is a real provider — a local-only setup (no cloud
    # keys) must not report "no free tier" and refuse to run.
    or OLLAMA_ENABLED
)

# Per-browser daily engagement quota. X-Client-Id is CALLER-ASSERTED, so this
# is a courtesy limit — it stops accidental over-use, not a determined abuser
# who simply sends a fresh id per request.
DAILY_ENGAGEMENT_QUOTA = int(_env("STRATAGENT_DAILY_QUOTA", "5"))

# The real abuse control: a per-IP ceiling the caller cannot choose. Set higher
# than the per-browser quota so shared networks (an office, a university) aren't
# punished, while a single actor cycling client-ids still hits a wall.
# 0 disables it (useful for a private/self-hosted instance where every visitor
# is trusted).
DAILY_IP_QUOTA = int(_env("STRATAGENT_DAILY_IP_QUOTA", "15"))

# Data retention. Engagements (case prompt, report, event log, telemetry) are
# HARD-deleted this many days after they start. The product has no signup, so
# there is no channel through which a user could later ask us to delete their
# data — an automatic purge is the honest substitute. 0 disables it (a private,
# single-operator instance may want to keep everything).
RETENTION_DAYS = float(_env("STRATAGENT_RETENTION_DAYS", "5"))
# How often the purge sweep runs. Cheap (one indexed DELETE), so hourly keeps
# the window tight without depending on an external cron.
PURGE_INTERVAL_SECONDS = float(_env("STRATAGENT_PURGE_INTERVAL", "3600"))

# IPs are PII, and this product's whole promise is that we hold nothing about
# you. So we store a salted HASH — enough to count requests per source, useless
# for identifying anyone, and unlinkable across deployments. A random per-boot
# salt is the safe default: quotas then reset on restart, which is the failure
# we want (over-permissive for a moment) rather than a durable IP record.
IP_HASH_SALT = _env("STRATAGENT_IP_SALT", "") or secrets.token_hex(16)

# Behind a reverse proxy (Railway/Fly/Render/nginx) the socket peer is the
# proxy, so every visitor looks like one IP and the quota would lock everyone
# out. Set to 1 there to read the client from X-Forwarded-For.
# MUST stay 0 when directly exposed: X-Forwarded-For is caller-supplied, and
# trusting it without a proxy in front hands the attacker the bypass we just
# closed.
TRUST_PROXY = _env("STRATAGENT_TRUST_PROXY", "0") == "1"

# CORS origins for the frontend, comma-separated.
CORS_ORIGINS = [
    o.strip()
    for o in _env("STRATAGENT_CORS_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]
