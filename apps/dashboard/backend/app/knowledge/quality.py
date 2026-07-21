"""Generic framework quality checks (requester's "Quality Model" section).

**Generic, not per-framework** — every check function here works off a
framework's DECLARED metadata (``required_inputs``, ``required_evidence``,
``dependencies``, ``confidence_model``) plus the caller's
``FrameworkExecutionRequest``, never framework-specific code. This is the
concrete mechanism behind ``FrameworkQualityGate.check_kind`` being a string
key into ``_CHECKS`` rather than a callable baked into the catalog — the same
principle ``app.consulting.quality_gates`` established one layer up.

**Fails gracefully** (requester's own words): every check function here
reports a ``passed=False`` result, never raises — a framework with
insufficient inputs is a normal, expected outcome to report, not an error.
"""

from __future__ import annotations

from collections.abc import Callable

from app.knowledge.models import (
    FrameworkDefinition,
    FrameworkExecutionRequest,
    FrameworkQualityGate,
    FrameworkQualityGateCheckResult,
    FrameworkQualityGateResult,
)


def _loose_match(needle: str, haystacks: tuple[str, ...]) -> bool:
    n = needle.lower()
    return any(n in h.lower() or h.lower() in n for h in haystacks)


def _check_required_inputs_present(
    framework: FrameworkDefinition, request: FrameworkExecutionRequest
) -> list[FrameworkQualityGateCheckResult]:
    checks = []
    for ri in framework.required_inputs:
        present = _loose_match(ri, request.provided_inputs)
        checks.append(
            FrameworkQualityGateCheckResult(
                name=f"input:{ri}",
                passed=present,
                detail="" if present else "not supplied",
            )
        )
    if not checks:
        checks.append(FrameworkQualityGateCheckResult("no_required_inputs", True))
    return checks


def _check_required_evidence_present(
    framework: FrameworkDefinition, request: FrameworkExecutionRequest
) -> list[FrameworkQualityGateCheckResult]:
    checks = []
    for re_ in framework.required_evidence:
        present = _loose_match(re_, request.provided_evidence)
        checks.append(
            FrameworkQualityGateCheckResult(
                name=f"evidence:{re_}",
                passed=present,
                detail="" if present else "not supplied",
            )
        )
    if not checks:
        checks.append(FrameworkQualityGateCheckResult("no_required_evidence", True))
    return checks


def _check_dependency_completion(
    framework: FrameworkDefinition, request: FrameworkExecutionRequest
) -> list[FrameworkQualityGateCheckResult]:
    checks = []
    for dep in framework.dependencies:
        done = dep in request.completed_dependency_ids
        checks.append(
            FrameworkQualityGateCheckResult(
                name=f"dependency:{dep}",
                passed=done,
                detail="" if done else "not yet executed",
            )
        )
    if not checks:
        checks.append(FrameworkQualityGateCheckResult("no_dependencies", True))
    return checks


def _check_minimum_inputs(
    framework: FrameworkDefinition, request: FrameworkExecutionRequest
) -> list[FrameworkQualityGateCheckResult]:
    has_any = len(request.provided_inputs) > 0 or not framework.required_inputs
    return [FrameworkQualityGateCheckResult("minimum_inputs", has_any)]


def _check_analysis_completeness(
    framework: FrameworkDefinition, request: FrameworkExecutionRequest
) -> list[FrameworkQualityGateCheckResult]:
    return [
        FrameworkQualityGateCheckResult("has_analyses", len(request.analyses) > 0),
        FrameworkQualityGateCheckResult("has_findings", len(request.findings) > 0),
    ]


def _check_confidence_threshold(
    framework: FrameworkDefinition, request: FrameworkExecutionRequest
) -> list[FrameworkQualityGateCheckResult]:
    confidence = request.confidence if request.confidence is not None else 0.0
    threshold = framework.confidence_model.min_threshold
    passed = confidence >= threshold
    return [
        FrameworkQualityGateCheckResult(
            "confidence_threshold",
            passed,
            "" if passed else f"{confidence:.2f} < required {threshold:.2f}",
        )
    ]


def _check_internal_consistency(
    framework: FrameworkDefinition, request: FrameworkExecutionRequest
) -> list[FrameworkQualityGateCheckResult]:
    # A recommendation with zero backing findings is internally inconsistent
    # — the same "no unsupported findings" discipline app.consulting enforces.
    consistent = not request.recommendations or len(request.findings) > 0
    return [
        FrameworkQualityGateCheckResult(
            "recommendations_backed_by_findings",
            consistent,
            "" if consistent else "recommendations present with zero findings",
        )
    ]


def _check_calculation_validity(
    framework: FrameworkDefinition, request: FrameworkExecutionRequest
) -> list[FrameworkQualityGateCheckResult]:
    valid = not request.calculations or request.calculations_verified
    return [
        FrameworkQualityGateCheckResult(
            "calculations_verified",
            valid,
            "" if valid else "calculations present but not marked verified",
        )
    ]


CheckFn = Callable[
    [FrameworkDefinition, FrameworkExecutionRequest],
    list[FrameworkQualityGateCheckResult],
]

_CHECKS: dict[str, CheckFn] = {
    "required_inputs_present": _check_required_inputs_present,
    "required_evidence_present": _check_required_evidence_present,
    "dependency_completion": _check_dependency_completion,
    "minimum_inputs": _check_minimum_inputs,
    "analysis_completeness": _check_analysis_completeness,
    "confidence_threshold": _check_confidence_threshold,
    "internal_consistency": _check_internal_consistency,
    "calculation_validity": _check_calculation_validity,
}


def evaluate_gate(
    gate: FrameworkQualityGate,
    framework: FrameworkDefinition,
    request: FrameworkExecutionRequest,
) -> FrameworkQualityGateResult:
    check_fn = _CHECKS.get(gate.check_kind)
    if check_fn is None:
        # An unrecognized check_kind fails gracefully as a single failed
        # check, never an exception — a broken catalog entry must not crash
        # execution.
        checks = [
            FrameworkQualityGateCheckResult(
                "unknown_check_kind",
                False,
                f"no check registered for {gate.check_kind!r}",
            )
        ]
    else:
        checks = check_fn(framework, request)
    return FrameworkQualityGateResult(
        gate_id=gate.id,
        mandatory=gate.mandatory,
        passed=all(c.passed for c in checks),
        checks=tuple(checks),
    )


def evaluate_gates(
    framework: FrameworkDefinition, request: FrameworkExecutionRequest
) -> tuple[FrameworkQualityGateResult, ...]:
    return tuple(evaluate_gate(g, framework, request) for g in framework.quality_gates)


def gates_pass(
    framework: FrameworkDefinition, request: FrameworkExecutionRequest
) -> bool:
    """True iff every MANDATORY gate passed — a non-mandatory gate failing
    never blocks execution, mirroring ``app.consulting.quality_gates``."""
    results = evaluate_gates(framework, request)
    return all(r.passed for r in results if r.mandatory)
