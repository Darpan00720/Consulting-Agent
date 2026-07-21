"""Tests for the generic framework quality checks."""

from __future__ import annotations

from app.knowledge.models import FrameworkExecutionRequest
from app.knowledge.quality import evaluate_gates, gates_pass
from app.knowledge.registry import default_framework_registry


def test_gates_fail_with_no_inputs_or_evidence():
    r = default_framework_registry()
    five_forces = r.get("five_forces")
    req = FrameworkExecutionRequest()
    assert not gates_pass(five_forces, req)


def test_gates_pass_with_all_inputs_and_evidence():
    r = default_framework_registry()
    five_forces = r.get("five_forces")
    req = FrameworkExecutionRequest(
        provided_inputs=("industry definition", "competitor list"),
        provided_evidence=("industry reports", "competitor financials"),
    )
    assert gates_pass(five_forces, req)


def test_dependency_completion_gate_blocks_until_dependencies_run():
    r = default_framework_registry()
    swot = r.get("swot")
    req_no_deps = FrameworkExecutionRequest(
        provided_inputs=("internal capability assessment", "external market scan"),
    )
    assert not gates_pass(swot, req_no_deps)
    req_with_deps = FrameworkExecutionRequest(
        provided_inputs=("internal capability assessment", "external market scan"),
        completed_dependency_ids=("five_forces", "pestle"),
    )
    assert gates_pass(swot, req_with_deps)


def test_unknown_check_kind_fails_gracefully_not_an_exception():
    import dataclasses

    from app.knowledge.models import FrameworkQualityGate

    r = default_framework_registry()
    base = r.get("five_forces")
    broken_gate = FrameworkQualityGate(
        id="gate.broken", check_kind="not_a_real_check", description="x"
    )
    broken = dataclasses.replace(base, quality_gates=(broken_gate,))
    results = evaluate_gates(broken, FrameworkExecutionRequest())
    assert len(results) == 1
    assert not results[0].passed
    assert "no check registered" in results[0].checks[0].detail


def test_minimum_inputs_check_kind():
    import dataclasses

    from app.knowledge.models import FrameworkQualityGate

    r = default_framework_registry()
    base = r.get("five_forces")
    gate = FrameworkQualityGate(id="g", check_kind="minimum_inputs", description="x")
    fw = dataclasses.replace(base, quality_gates=(gate,))
    assert not gates_pass(fw, FrameworkExecutionRequest())
    assert gates_pass(fw, FrameworkExecutionRequest(provided_inputs=("anything",)))


def test_analysis_completeness_check_kind():
    import dataclasses

    from app.knowledge.models import FrameworkQualityGate

    r = default_framework_registry()
    base = r.get("five_forces")
    gate = FrameworkQualityGate(
        id="g", check_kind="analysis_completeness", description="x"
    )
    fw = dataclasses.replace(base, quality_gates=(gate,))
    assert not gates_pass(fw, FrameworkExecutionRequest())
    assert gates_pass(fw, FrameworkExecutionRequest(analyses=("a",), findings=("f",)))


def test_confidence_threshold_check_kind():
    import dataclasses

    from app.knowledge.models import ConfidenceModel, FrameworkQualityGate

    r = default_framework_registry()
    base = r.get("five_forces")
    gate = FrameworkQualityGate(
        id="g", check_kind="confidence_threshold", description="x"
    )
    fw = dataclasses.replace(
        base,
        quality_gates=(gate,),
        confidence_model=ConfidenceModel(method="evidence_weighted", min_threshold=0.6),
    )
    assert not gates_pass(fw, FrameworkExecutionRequest(confidence=0.4))
    assert gates_pass(fw, FrameworkExecutionRequest(confidence=0.7))


def test_internal_consistency_check_kind_flags_unbacked_recommendations():
    import dataclasses

    from app.knowledge.models import FrameworkQualityGate

    r = default_framework_registry()
    base = r.get("five_forces")
    gate = FrameworkQualityGate(
        id="g", check_kind="internal_consistency", description="x"
    )
    fw = dataclasses.replace(base, quality_gates=(gate,))
    assert not gates_pass(fw, FrameworkExecutionRequest(recommendations=("do X",)))
    assert gates_pass(
        fw, FrameworkExecutionRequest(recommendations=("do X",), findings=("f",))
    )


def test_calculation_validity_check_kind():
    import dataclasses

    from app.knowledge.models import FrameworkQualityGate

    r = default_framework_registry()
    base = r.get("dcf")
    gate = FrameworkQualityGate(
        id="g", check_kind="calculation_validity", description="x"
    )
    fw = dataclasses.replace(base, quality_gates=(gate,))
    assert not gates_pass(fw, FrameworkExecutionRequest(calculations={"npv": 1000}))
    assert gates_pass(
        fw,
        FrameworkExecutionRequest(
            calculations={"npv": 1000}, calculations_verified=True
        ),
    )
