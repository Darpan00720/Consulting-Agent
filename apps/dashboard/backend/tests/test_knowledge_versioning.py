"""Tests for deprecation, replacement, backward compatibility, migration,
and execution history."""

from __future__ import annotations

import pytest

from app.knowledge.errors import DeprecatedFrameworkError
from app.knowledge.execution import execute_framework
from app.knowledge.models import ExecutionHistoryEntry, FrameworkExecutionRequest
from app.knowledge.registry import default_framework_registry
from app.knowledge.versioning import VersioningLedger


def test_mark_deprecated_and_is_deprecated():
    ledger = VersioningLedger()
    ledger.mark_deprecated("dcf", "1.0.0", reason="superseded by dcf_v2")
    assert ledger.is_deprecated("dcf", "1.0.0")
    assert not ledger.is_deprecated("npv", "1.0.0")


def test_backward_compatible_resolve_returns_deprecated_by_default():
    r = default_framework_registry()
    ledger = VersioningLedger()
    ledger.mark_deprecated("dcf", "1.0.0", reason="superseded")
    resolved = ledger.resolve(r, "dcf")
    assert resolved.id == "dcf"  # existing callers keep working


def test_resolve_with_migration_redirects_to_replacement():
    r = default_framework_registry()
    ledger = VersioningLedger()
    ledger.mark_deprecated("dcf", "1.0.0", replaced_by="npv", reason="simplify")
    resolved = ledger.resolve(r, "dcf", allow_deprecated=False)
    assert resolved.id == "npv"


def test_resolve_with_no_replacement_raises_when_migration_forced():
    r = default_framework_registry()
    ledger = VersioningLedger()
    ledger.mark_deprecated("dcf", "1.0.0", reason="retired, no successor")
    with pytest.raises(DeprecatedFrameworkError):
        ledger.resolve(r, "dcf", allow_deprecated=False)


def test_resolve_of_non_deprecated_framework_is_a_no_op():
    r = default_framework_registry()
    ledger = VersioningLedger()
    resolved = ledger.resolve(r, "five_forces", allow_deprecated=False)
    assert resolved.id == "five_forces"


def test_execution_history_is_append_only_and_queryable():
    r = default_framework_registry()
    ledger = VersioningLedger()
    five_forces = r.get("five_forces")
    req = FrameworkExecutionRequest(
        provided_inputs=("industry definition", "competitor list"),
        provided_evidence=("industry reports", "competitor financials"),
        findings=("x",),
    )
    result1 = execute_framework(five_forces, req)
    result2 = execute_framework(five_forces, req)
    ledger.record_execution(
        ExecutionHistoryEntry(
            execution_id=result1.id,
            framework_id=result1.framework_id,
            framework_version=result1.framework_version,
            success=result1.success,
            confidence=result1.confidence,
            executed_at=result1.executed_at,
        )
    )
    ledger.record_execution(
        ExecutionHistoryEntry(
            execution_id=result2.id,
            framework_id=result2.framework_id,
            framework_version=result2.framework_version,
            success=result2.success,
            confidence=result2.confidence,
            executed_at=result2.executed_at,
        )
    )
    history = ledger.history_for("five_forces")
    assert len(history) == 2
    assert {h.execution_id for h in history} == {result1.id, result2.id}


def test_history_for_framework_with_no_executions_is_empty():
    ledger = VersioningLedger()
    assert ledger.history_for("never_run") == ()
