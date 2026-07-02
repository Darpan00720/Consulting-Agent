"""Validation runner — the only place rules are orchestrated (adjustment 5).

Aggregates the per-group rule registries, runs each rule's (independent) validator,
attaches rule metadata to every finding, times the pass, and returns a
``ValidationReport``. Validators never call each other or the runner.
"""

from __future__ import annotations

import time

from common.errors import StratAgentError
from state.models import EngagementState
from state.validation.business import RULES as _BUSINESS
from state.validation.governance import RULES as _GOVERNANCE
from state.validation.lifecycle import RULES as _LIFECYCLE
from state.validation.referential import RULES as _REFERENTIAL
from state.validation.structural import RULES as _STRUCTURAL
from state.validation.types import (
    ValidationGroup,
    ValidationReport,
    ValidationRule,
    Violation,
    ViolationSeverity,
)

ALL_RULES: list[ValidationRule] = [
    *_STRUCTURAL,
    *_LIFECYCLE,
    *_REFERENTIAL,
    *_BUSINESS,
    *_GOVERNANCE,
]

_BLOCKING = (ViolationSeverity.ERROR, ViolationSeverity.FATAL)


class StateValidationError(StratAgentError):
    """Raised by ``raise_if_invalid`` when a state has blocking violations."""

    def __init__(self, report: ValidationReport) -> None:
        self.report = report
        blocking = [v for v in report.violations if v.severity in _BLOCKING]
        detail = "; ".join(f"[{v.rule_id}] {v.message}" for v in blocking)
        super().__init__(f"{len(blocking)} blocking violation(s): {detail}")


def validate(state: EngagementState) -> ValidationReport:
    """Run every rule against ``state`` and return a report (pure; no IO)."""
    start = time.perf_counter()
    violations: list[Violation] = []
    for rule in ALL_RULES:
        for finding in rule.validator(state):
            violations.append(
                Violation(
                    rule_id=rule.rule_id,
                    group=rule.group,
                    severity=rule.severity,
                    path=finding.path,
                    message=finding.message,
                    object_id=finding.object_id,
                )
            )
    duration_ms = (time.perf_counter() - start) * 1000
    counts = {severity: 0 for severity in ViolationSeverity}
    for violation in violations:
        counts[violation.severity] += 1
    valid = not any(v.severity in _BLOCKING for v in violations)
    return ValidationReport(
        valid=valid,
        violations=violations,
        counts=counts,
        duration_ms=duration_ms,
        groups_checked=list(ValidationGroup),
    )


def raise_if_invalid(state: EngagementState) -> None:
    """Validate and raise ``StateValidationError`` if the state is invalid."""
    report = validate(state)
    if not report.valid:
        raise StateValidationError(report)
