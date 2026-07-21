"""Tests for the generic framework execution engine."""

from __future__ import annotations

from app.knowledge.execution import execute_framework
from app.knowledge.models import FrameworkExecutionRequest
from app.knowledge.registry import default_framework_registry


def test_execution_fails_gracefully_when_readiness_gates_fail():
    r = default_framework_registry()
    five_forces = r.get("five_forces")
    result = execute_framework(five_forces, FrameworkExecutionRequest())
    assert result.success is False
    assert "gate.five_forces.inputs" in result.error
    assert result.recommendations == ()  # never generates recommendations on failure


def test_execution_succeeds_and_produces_structured_output():
    r = default_framework_registry()
    five_forces = r.get("five_forces")
    req = FrameworkExecutionRequest(
        provided_inputs=("industry definition", "competitor list"),
        provided_evidence=("industry reports", "competitor financials"),
        questions=("How intense is rivalry?",),
        analyses=("5 comparable competitors",),
        findings=("Industry rated 3.8/5 unattractive",),
        recommendations=("Entry requires differentiation",),
        next_analyses=("Run TAM/SAM/SOM",),
    )
    result = execute_framework(five_forces, req)
    assert result.success
    assert result.framework_id == "five_forces"
    assert result.findings == ("Industry rated 3.8/5 unattractive",)
    assert result.recommendations == ("Entry requires differentiation",)
    assert result.next_analyses == ("Run TAM/SAM/SOM",)
    assert result.quality_gate_results


def test_execution_never_generates_engagement_recommendations_directly():
    """Framework-level ``recommendations`` are analytical implications, not
    an engagement recommendation — this is a data-shape check confirming the
    field never becomes anything but plain strings the caller supplied."""
    r = default_framework_registry()
    dcf = r.get("dcf")
    req = FrameworkExecutionRequest(
        provided_inputs=("cash flow projections", "discount rate"),
        provided_evidence=("financial statements",),
        findings=("NPV is $4.2M",),
        recommendations=("Valuation supports the business case",),
        calculations={"npv": 4_200_000},
        calculations_verified=True,
    )
    result = execute_framework(dcf, req)
    assert result.success
    assert all(isinstance(r, str) for r in result.recommendations)


def test_confidence_is_derived_from_confidence_model_when_not_supplied():
    r = default_framework_registry()
    five_forces = r.get("five_forces")  # confidence_model.method == "evidence_weighted"
    req_full = FrameworkExecutionRequest(
        provided_inputs=("industry definition", "competitor list"),
        provided_evidence=("industry reports", "competitor financials"),
        findings=("x",),
    )
    req_partial = FrameworkExecutionRequest(
        provided_inputs=("industry definition", "competitor list"),
        provided_evidence=("industry reports",),  # only 1 of 2
        findings=("x",),
    )
    full_result = execute_framework(five_forces, req_full)
    partial_result = execute_framework(five_forces, req_partial)
    assert full_result.confidence > partial_result.confidence


def test_caller_supplied_confidence_is_respected():
    r = default_framework_registry()
    five_forces = r.get("five_forces")
    req = FrameworkExecutionRequest(
        provided_inputs=("industry definition", "competitor list"),
        provided_evidence=("industry reports", "competitor financials"),
        confidence=0.33,
    )
    result = execute_framework(five_forces, req)
    assert result.confidence == 0.33


def test_limitations_combine_framework_declared_and_execution_specific():
    r = default_framework_registry()
    five_forces = r.get("five_forces")
    req = FrameworkExecutionRequest(
        provided_inputs=("industry definition", "competitor list"),
        provided_evidence=("industry reports", "competitor financials"),
        limitations=("Data is 6 months stale",),
    )
    result = execute_framework(five_forces, req)
    assert "Data is 6 months stale" in result.limitations
    assert len(result.limitations) > 1  # framework's own declared limitation too
