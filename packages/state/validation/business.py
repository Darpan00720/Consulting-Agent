"""Business rules — cross-field consulting invariants (ADR-002 §Validation Rules)."""

from __future__ import annotations

from state.ledgers import AssumptionStatus
from state.models import EngagementState
from state.validation._util import analysis_blocks
from state.validation.types import (
    Finding,
    ValidationGroup,
    ValidationRule,
    ViolationSeverity,
)


def _confidence_bounded_by_evidence(state: EngagementState) -> list[Finding]:
    rec = state.recommendations
    report = state.confidence
    if rec is None or rec.decision is None or report is None or report.overall is None:
        return []
    validated = [e.confidence for e in state.evidence if e.validated]
    if not validated:
        return []
    floor = min(validated)
    if report.overall > floor:
        return [
            Finding(
                path="confidence.overall",
                message=(
                    f"overall confidence {report.overall} exceeds the minimum "
                    f"validated-evidence confidence {floor}"
                ),
            )
        ]
    return []


def _recommendation_has_validated_evidence(state: EngagementState) -> list[Finding]:
    rec = state.recommendations
    if rec is None or rec.decision is None:
        return []
    if not any(e.validated for e in state.evidence):
        return [
            Finding(
                path="recommendations",
                message="recommendation has no validated supporting evidence",
                object_id=rec.id,
            )
        ]
    return []


def _not_resting_on_invalidated_assumptions(state: EngagementState) -> list[Finding]:
    rec = state.recommendations
    if rec is None or rec.decision is None:
        return []
    invalidated = {
        a.id for a in state.assumptions if a.status is AssumptionStatus.INVALIDATED
    }
    findings: list[Finding] = []
    for attr, block in analysis_blocks(state):
        for index, finding in enumerate(block.findings):
            for ref in finding.assumption_refs:
                if ref in invalidated:
                    findings.append(
                        Finding(
                            path=f"{attr}.findings[{index}].assumption_refs",
                            message=f"rests on invalidated assumption {ref!r}",
                            object_id=finding.id,
                        )
                    )
    return findings


RULES = [
    ValidationRule(
        "BIZ-001",
        ValidationGroup.BUSINESS,
        ViolationSeverity.ERROR,
        "ADR-002 §Validation Rules",
        "Overall confidence does not exceed the minimum validated-evidence confidence.",
        _confidence_bounded_by_evidence,
    ),
    ValidationRule(
        "BIZ-002",
        ValidationGroup.BUSINESS,
        ViolationSeverity.ERROR,
        "ADR-002 §Validation Rules",
        "A recommendation with a decision has at least one validated evidence item.",
        _recommendation_has_validated_evidence,
    ),
    ValidationRule(
        "BIZ-003",
        ValidationGroup.BUSINESS,
        ViolationSeverity.WARNING,
        "ADR-002 §9",
        "A recommendation does not rest on invalidated assumptions.",
        _not_resting_on_invalidated_assumptions,
    ),
]
