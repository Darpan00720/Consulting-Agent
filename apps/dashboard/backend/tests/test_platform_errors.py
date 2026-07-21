"""Tests for the top-level error boundary (ADR-013 W6, requirement 7/13).

Normalize, classify, redact, correlate trace_id, safe logging, recovery
guidance — and confirms a raw internal exception never reaches a caller
through this boundary.
"""

from __future__ import annotations

from app.agents.errors import ExecutionFailure as AgentExecutionFailure
from app.memory.errors import QueryFailure as MemoryQueryFailure
from app.platform.errors import PlatformError, normalize_error, safe_log
from app.tools.errors import Timeout as ToolTimeout


def test_normalize_returns_platform_error():
    result = normalize_error(RuntimeError("boom"))
    assert isinstance(result, PlatformError)


def test_classification_by_originating_layer():
    assert normalize_error(AgentExecutionFailure("x")).category == "agent"
    assert normalize_error(MemoryQueryFailure("x")).category == "memory"
    assert normalize_error(ToolTimeout("x")).category == "tool"


def test_unclassifiable_exception_is_unknown():
    result = normalize_error(ValueError("generic"))
    assert result.category == "unknown"


def test_trace_id_is_correlated():
    result = normalize_error(RuntimeError("x"), trace_id="err-trace-1")
    assert result.trace_id == "err-trace-1"


def test_trace_id_defaults_to_none():
    result = normalize_error(RuntimeError("x"))
    assert result.trace_id is None


def test_original_type_preserved():
    result = normalize_error(ValueError("x"))
    assert result.original_type == "ValueError"


def test_every_category_has_recovery_guidance():
    for exc in (
        AgentExecutionFailure("x"),
        MemoryQueryFailure("x"),
        ToolTimeout("x"),
        ValueError("x"),
    ):
        result = normalize_error(exc)
        assert result.recovery_guidance  # non-empty


# ---- Redaction --------------------------------------------------------------


def test_redacts_anthropic_key():
    result = normalize_error(
        RuntimeError("failed with key sk-ant-api03-abcdefghijklmnop1234")
    )
    assert "sk-ant-" not in result.message
    assert "[REDACTED]" in result.message


def test_redacts_openai_style_key():
    result = normalize_error(
        RuntimeError("key sk-proj-abcdefghijklmnopqrstuvwxyz1234567890 leaked")
    )
    assert "sk-proj-" not in result.message


def test_redacts_gemini_key():
    result = normalize_error(
        RuntimeError("bad key AIzaSyAbcdefghijklmnopqrstuvwxyz1234")
    )
    assert "AIza" not in result.message


def test_redacts_github_token():
    result = normalize_error(
        RuntimeError("token ghp_abcdefghijklmnopqrstuvwxyz1234567890")
    )
    assert "ghp_" not in result.message


def test_redacts_bearer_token():
    result = normalize_error(RuntimeError("Authorization: Bearer abc123def456ghi789"))
    assert "Bearer abc123" not in result.message


def test_non_credential_text_is_not_redacted():
    result = normalize_error(
        RuntimeError("agent 'claude' does not support workflow 'coding'")
    )
    assert "claude" in result.message
    assert "coding" in result.message


# ---- Safe logging (requirement 7) ------------------------------------------


def test_safe_log_emits_a_correlated_line(caplog):
    import logging

    logger = logging.getLogger("test.platform.errors")
    with caplog.at_level("ERROR", logger="test.platform.errors"):
        safe_log(logger, RuntimeError("boom"), trace_id="log-trace-1")
    line = next(
        r.getMessage() for r in caplog.records if "platform-error" in r.getMessage()
    )
    assert "trace_id=log-trace-1" in line
    assert "category=" in line


def test_safe_log_returns_the_normalized_error():
    import logging

    logger = logging.getLogger("test.platform.errors")
    result = safe_log(logger, RuntimeError("boom"), trace_id="t")
    assert isinstance(result, PlatformError)


def test_safe_log_redacts_in_the_log_line(caplog):
    import logging

    logger = logging.getLogger("test.platform.errors")
    with caplog.at_level("ERROR", logger="test.platform.errors"):
        safe_log(
            logger, RuntimeError("key sk-ant-api03-abcdefghijklmnop1234"), trace_id="t"
        )
    line = next(
        r.getMessage() for r in caplog.records if "platform-error" in r.getMessage()
    )
    assert "sk-ant-" not in line
