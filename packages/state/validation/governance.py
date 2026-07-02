"""Governance rules — gate and approval discipline (ADR-002 §Validation Rules)."""

from __future__ import annotations

from state.models import EngagementState
from state.sections.enums import (
    ChallengeVerdict,
    GateResult,
    RecommendationStatus,
    ReviewVerdict,
)
from state.validation._util import has_pass_gate
from state.validation.types import (
    Finding,
    ValidationGroup,
    ValidationRule,
    ViolationSeverity,
)


def _acceptance_requires_gates(state: EngagementState) -> list[Finding]:
    rec = state.recommendations
    if rec is None or rec.status is not RecommendationStatus.ACCEPTED:
        return []
    missing = [g for g in ("reviewer", "challenger") if not has_pass_gate(state, g)]
    if not missing:
        return []
    return [
        Finding(
            path="recommendations.status",
            message=f"accepted without passing gate(s): {', '.join(missing)}",
            object_id=rec.id,
        )
    ]


def _rejections_have_actionable_fix(state: EngagementState) -> list[Finding]:
    findings: list[Finding] = []
    reviewer = state.reviewer_notes
    if (
        reviewer is not None
        and reviewer.verdict is ReviewVerdict.NEEDS_REWORK
        and not reviewer.issues
    ):
        findings.append(
            Finding(
                path="reviewer_notes.issues",
                message="reviewer 'needs_rework' verdict lists no actionable issues",
                object_id=reviewer.id,
            )
        )
    challenge = state.challenge_notes
    if (
        challenge is not None
        and challenge.verdict is ChallengeVerdict.NEEDS_REWORK
        and not challenge.counter_case
    ):
        findings.append(
            Finding(
                path="challenge_notes.counter_case",
                message="challenger 'needs_rework' verdict has no counter_case",
                object_id=challenge.id,
            )
        )
    return findings


def _fail_gates_have_rework(state: EngagementState) -> list[Finding]:
    findings: list[Finding] = []
    reviewer = state.reviewer_notes
    challenge = state.challenge_notes
    for index, gate in enumerate(state.quality_gates):
        if gate.result is not GateResult.FAIL:
            continue
        if gate.gate == "reviewer" and (
            reviewer is None or reviewer.verdict is not ReviewVerdict.NEEDS_REWORK
        ):
            findings.append(
                Finding(
                    path=f"quality_gates[{index}]",
                    message="failed reviewer gate without a 'needs_rework' verdict",
                    object_id=gate.id,
                )
            )
        if gate.gate == "challenger" and (
            challenge is None or challenge.verdict is not ChallengeVerdict.NEEDS_REWORK
        ):
            findings.append(
                Finding(
                    path=f"quality_gates[{index}]",
                    message="failed challenger gate without a 'needs_rework' verdict",
                    object_id=gate.id,
                )
            )
    return findings


RULES = [
    ValidationRule(
        "GOV-001",
        ValidationGroup.GOVERNANCE,
        ViolationSeverity.ERROR,
        "ADR-002 §Validation Rules / Approval",
        "Recommendation acceptance requires reviewer + challenger gates passed.",
        _acceptance_requires_gates,
    ),
    ValidationRule(
        "GOV-002",
        ValidationGroup.GOVERNANCE,
        ViolationSeverity.ERROR,
        "ADR-002 §Validation Rules / Approval",
        "A 'needs_rework' verdict carries an actionable fix (issues / counter_case).",
        _rejections_have_actionable_fix,
    ),
    ValidationRule(
        "GOV-003",
        ValidationGroup.GOVERNANCE,
        ViolationSeverity.WARNING,
        "ADR-002 §Validation Rules",
        "A failed gate has a corresponding 'needs_rework' verdict recorded.",
        _fail_gates_have_rework,
    ),
]
