"""Lifecycle rules — phase preconditions and transition legality (ADR-002 §2)."""

from __future__ import annotations

from state.enums import LifecycleStatus
from state.models import EngagementState
from state.sections.enums import DeliverableKind, RecommendationStatus
from state.validation._util import has_pass_gate
from state.validation.types import (
    Finding,
    ValidationGroup,
    ValidationRule,
    ViolationSeverity,
)

_FORWARD = [
    LifecycleStatus.INTAKE,
    LifecycleStatus.CLASSIFYING,
    LifecycleStatus.GAP_ANALYSIS,
    LifecycleStatus.PLANNING,
    LifecycleStatus.FRAMING,
    LifecycleStatus.ISSUE_TREE,
    LifecycleStatus.KNOWLEDGE,
    LifecycleStatus.ANALYSIS,
    LifecycleStatus.EVIDENCE_VALIDATION,
    LifecycleStatus.REVIEW,
    LifecycleStatus.CHALLENGE,
    LifecycleStatus.REPORTING,
    LifecycleStatus.COMPLETED,
]
_TERMINAL = {LifecycleStatus.FAILED, LifecycleStatus.ABORTED}


def _build_allowed() -> dict[LifecycleStatus, set[LifecycleStatus]]:
    allowed: dict[LifecycleStatus, set[LifecycleStatus]] = {}
    for i, phase in enumerate(_FORWARD):
        nxt: set[LifecycleStatus] = set(_TERMINAL)
        if i + 1 < len(_FORWARD):
            nxt.add(_FORWARD[i + 1])
        allowed[phase] = nxt
    # Rework loops (gates can send the engagement back to analysis).
    allowed[LifecycleStatus.REVIEW].add(LifecycleStatus.ANALYSIS)
    allowed[LifecycleStatus.CHALLENGE].add(LifecycleStatus.ANALYSIS)
    allowed[LifecycleStatus.COMPLETED] = set()
    for terminal in _TERMINAL:
        allowed[terminal] = set()
    return allowed


_ALLOWED = _build_allowed()


def _reporting_requires_gates(state: EngagementState) -> list[Finding]:
    if state.status not in (LifecycleStatus.REPORTING, LifecycleStatus.COMPLETED):
        return []
    missing = [g for g in ("reviewer", "challenger") if not has_pass_gate(state, g)]
    if not missing:
        return []
    gates = ", ".join(missing)
    return [
        Finding(
            path="quality_gates",
            message=f"{state.status.value!r} reached without gate(s): {gates}",
        )
    ]


def _completed_requires_outputs(state: EngagementState) -> list[Finding]:
    if state.status is not LifecycleStatus.COMPLETED:
        return []
    findings: list[Finding] = []
    if not any(d.kind is DeliverableKind.REPORT for d in state.deliverables):
        findings.append(
            Finding(
                path="deliverables",
                message="completed engagement has no report deliverable",
            )
        )
    rec = state.recommendations
    if rec is None or rec.status is not RecommendationStatus.ACCEPTED:
        findings.append(
            Finding(
                path="recommendations.status",
                message="completed engagement has no accepted recommendation",
            )
        )
    return findings


def _transitions_are_legal(state: EngagementState) -> list[Finding]:
    history = state.phase_history
    findings: list[Finding] = []
    for i in range(len(history) - 1):
        frm, to = history[i].phase, history[i + 1].phase
        if to not in _ALLOWED.get(frm, set()):
            findings.append(
                Finding(
                    path=f"phase_history[{i + 1}]",
                    message=f"illegal transition {frm.value} -> {to.value}",
                    object_id=history[i + 1].id,
                )
            )
    return findings


def _status_matches_history(state: EngagementState) -> list[Finding]:
    if state.phase_history and state.phase_history[-1].phase is not state.status:
        last = state.phase_history[-1].phase.value
        return [
            Finding(
                path="status",
                message=f"status {state.status.value!r} != last phase {last!r}",
            )
        ]
    return []


RULES = [
    ValidationRule(
        "LIFE-001",
        ValidationGroup.LIFECYCLE,
        ViolationSeverity.ERROR,
        "ADR-002 §Validation Rules",
        "reporting/completed requires reviewer + challenger gates passed.",
        _reporting_requires_gates,
    ),
    ValidationRule(
        "LIFE-002",
        ValidationGroup.LIFECYCLE,
        ViolationSeverity.ERROR,
        "ADR-002 §Validation Rules",
        "A completed engagement has a report and an accepted recommendation.",
        _completed_requires_outputs,
    ),
    ValidationRule(
        "LIFE-003",
        ValidationGroup.LIFECYCLE,
        ViolationSeverity.ERROR,
        "ADR-002 §Validation Rules",
        "Recorded phase transitions are legal.",
        _transitions_are_legal,
    ),
    ValidationRule(
        "LIFE-004",
        ValidationGroup.LIFECYCLE,
        ViolationSeverity.WARNING,
        "ADR-002 §2",
        "Current status matches the last recorded phase.",
        _status_matches_history,
    ),
]
