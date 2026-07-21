"""Top-level error boundary (requirement 7).

Every layer already has its OWN typed error hierarchy and "never raise past
my boundary" discipline (``app.workflow`` fails open internally; ``app.agents.
errors.AgentError``; ``app.memory.errors.MemoryError``;
``app.tools.errors.ToolError``). This module is the OUTER boundary — for a
caller sitting above all five layers (a future API endpoint, a CLI, this
platform package's own diagnostics) that wants ONE consistent error shape
regardless of which internal layer actually failed. It does not change how
any layer raises or reports internally.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_REDACT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}"),  # Anthropic
    re.compile(r"sk-proj-[A-Za-z0-9_-]{10,}"),  # OpenAI project key
    re.compile(r"sk-or-v1-[A-Za-z0-9_-]{10,}"),  # OpenRouter
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),  # generic OpenAI-shaped
    re.compile(r"gsk_[A-Za-z0-9_-]{10,}"),  # Groq
    re.compile(r"csk-[A-Za-z0-9_-]{10,}"),  # Cerebras
    re.compile(r"AIza[A-Za-z0-9_-]{20,}"),  # Google/Gemini
    re.compile(r"gh[pousr]_[A-Za-z0-9_-]{20,}"),  # GitHub tokens
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{10,}"),  # generic bearer token
)

_CATEGORY_BY_MODULE_PREFIX: tuple[tuple[str, str], ...] = (
    ("app.workflow", "routing"),
    ("app.agents", "agent"),
    ("app.memory", "memory"),
    ("app.tools", "tool"),
    ("app.pipeline.providers", "provider"),
    ("openai", "provider"),
)

_RECOVERY_GUIDANCE: dict[str, str] = {
    "routing": (
        "Check the Workflow Router's classification signals "
        "(command/skill/agent/text) for this request."
    ),
    "dispatch": "Inspect the Dispatcher's attempts/transitions for the failed target.",
    "agent": (
        "Check the failing agent's health() and supported_workflows; "
        "verify required credentials/tools."
    ),
    "memory": (
        "Check the resolved memory provider's health(); verify the "
        "requested memory type has a registered provider."
    ),
    "tool": "Check the resolved tool's health() and the permission policy decision.",
    "provider": "Check API keys / rate limits for the LLM provider chain (ADR-012).",
    "configuration": "Re-run validate_platform() to see the specific issue.",
    "unknown": "No guidance — check the original exception type and module.",
}


@dataclass(frozen=True)
class PlatformError:
    """The one, uniform error shape every platform-boundary caller receives
    (requirement 7). Never carries a raw exception object — only a redacted
    string and a classification."""

    category: str
    message: str
    trace_id: str | None
    recovery_guidance: str
    original_type: str


def _redact(message: str) -> str:
    for pattern in _REDACT_PATTERNS:
        message = pattern.sub("[REDACTED]", message)
    return message


def _classify(exc: Exception) -> str:
    module = type(exc).__module__
    for prefix, category in _CATEGORY_BY_MODULE_PREFIX:
        if module.startswith(prefix):
            return category
    return "unknown"


def normalize_error(exc: Exception, *, trace_id: str | None = None) -> PlatformError:
    """Normalize + classify + redact + attach recovery guidance
    (requirement 7). This is the ONLY sanctioned way a raw internal
    exception should reach a platform-boundary caller — always through this
    function, never directly."""
    category = _classify(exc)
    return PlatformError(
        category=category,
        message=_redact(str(exc)),
        trace_id=trace_id,
        recovery_guidance=_RECOVERY_GUIDANCE.get(
            category, _RECOVERY_GUIDANCE["unknown"]
        ),
        original_type=type(exc).__name__,
    )


def safe_log(logger, exc: Exception, *, trace_id: str | None = None) -> PlatformError:
    """Normalize an exception AND log it safely (redacted, one line,
    correlated by trace_id) — the "safe logging" requirement 7 asks for."""
    normalized = normalize_error(exc, trace_id=trace_id)
    logger.error(
        "platform-error trace_id=%s category=%s original_type=%s message=%s",
        trace_id,
        normalized.category,
        normalized.original_type,
        normalized.message,
    )
    return normalized
