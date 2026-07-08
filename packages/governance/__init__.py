"""Governance capability — gate enforcement and lifecycle transition validation."""

from __future__ import annotations

from governance.gates import (
    GateCheckResult,
    GovernanceGateError,
    check_challenger_can_run,
    check_reporting_gate,
    check_reviewer_can_run,
    enforce_challenger_gate,
    enforce_reporting_gate,
    enforce_reviewer_gate,
)
from governance.transitions import (
    TransitionError,
    is_transition_allowed,
    validate_transition,
)

__all__ = [
    "GateCheckResult",
    "GovernanceGateError",
    "TransitionError",
    "check_challenger_can_run",
    "check_reporting_gate",
    "check_reviewer_can_run",
    "enforce_challenger_gate",
    "enforce_reporting_gate",
    "enforce_reviewer_gate",
    "is_transition_allowed",
    "validate_transition",
]
