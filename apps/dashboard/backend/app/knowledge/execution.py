"""Generic framework execution engine (requester's "Framework Execution"
section).

Pure function, no I/O, no LLM call — every analytical field in
``FrameworkExecutionRequest`` is supplied by the caller (an analyst agent
that has already done the actual thinking/calculating). This engine's job is
narrow and generic: validate readiness via ``quality.py``, derive a
confidence score from the framework's declared ``ConfidenceModel`` (only
when the caller doesn't supply its own), and package everything into a
structured ``FrameworkExecutionResult``.

**"Framework execution must never directly generate executive
recommendations"** is enforced structurally, not just documented:
``FrameworkExecutionResult.recommendations`` holds framework-level
analytical implications only ("this force is a major threat" — never
"launch in Q3"); see ``integration.py``, which is the ONLY code that reads a
``FrameworkExecutionResult`` and feeds a real engagement, and which
deliberately exposes no path from a framework result into
``app.consulting.tracking.create_recommendation`` — only into evidence and
analysis findings, leaving the actual recommendation as a judgment call made
downstream, same as every other analysis in this platform.
"""

from __future__ import annotations

from app.knowledge import quality
from app.knowledge.models import (
    ConfidenceModel,
    FrameworkDefinition,
    FrameworkExecutionRequest,
    FrameworkExecutionResult,
    new_execution_id,
)


def _loose_match(needle: str, haystacks: tuple[str, ...]) -> bool:
    n = needle.lower()
    return any(n in h.lower() or h.lower() in n for h in haystacks)


def _readiness_ratio(required: tuple[str, ...], available: tuple[str, ...]) -> float:
    if not required:
        return 1.0
    matched = sum(1 for r in required if _loose_match(r, available))
    return matched / len(required)


def _derive_confidence(
    framework: FrameworkDefinition,
    request: FrameworkExecutionRequest,
    gate_pass_ratio: float,
) -> float:
    model: ConfidenceModel = framework.confidence_model
    if model.method == "evidence_weighted":
        readiness = _readiness_ratio(
            framework.required_evidence, request.provided_evidence
        )
    elif model.method == "data_completeness":
        readiness = _readiness_ratio(framework.required_inputs, request.provided_inputs)
    else:  # "expert_judgment" or any other declared method — no automatic signal
        readiness = 1.0
    return (gate_pass_ratio + readiness) / 2


def execute_framework(
    framework: FrameworkDefinition, request: FrameworkExecutionRequest
) -> FrameworkExecutionResult:
    """Never raises (fails gracefully, per the requester's own wording): a
    mandatory-gate failure produces ``success=False`` with the specific
    failed gate ids named in ``error`` — never an exception."""
    gate_results = quality.evaluate_gates(framework, request)
    mandatory_results = [g for g in gate_results if g.mandatory]
    gate_pass_ratio = (
        sum(1 for g in mandatory_results if g.passed) / len(mandatory_results)
        if mandatory_results
        else 1.0
    )
    gates_ok = all(g.passed for g in mandatory_results)

    confidence = request.confidence
    if confidence is None:
        confidence = _derive_confidence(framework, request, gate_pass_ratio)
    confidence = min(1.0, max(0.0, confidence))

    combined_limitations = (*framework.limitations, *request.limitations)

    if not gates_ok:
        failed_ids = [g.gate_id for g in mandatory_results if not g.passed]
        return FrameworkExecutionResult(
            id=new_execution_id(),
            framework_id=framework.id,
            framework_version=framework.version,
            questions=request.questions,
            analyses=request.analyses,
            calculations=request.calculations,
            findings=request.findings,
            confidence=confidence,
            recommendations=(),
            limitations=combined_limitations,
            next_analyses=request.next_analyses,
            quality_gate_results=gate_results,
            success=False,
            error=f"mandatory quality gate(s) failed: {', '.join(failed_ids)}",
        )

    return FrameworkExecutionResult(
        id=new_execution_id(),
        framework_id=framework.id,
        framework_version=framework.version,
        questions=request.questions,
        analyses=request.analyses,
        calculations=request.calculations,
        findings=request.findings,
        confidence=confidence,
        recommendations=request.recommendations,
        limitations=combined_limitations,
        next_analyses=request.next_analyses,
        quality_gate_results=gate_results,
        success=True,
        error=None,
    )
