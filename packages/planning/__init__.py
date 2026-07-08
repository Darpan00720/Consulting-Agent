"""Planning capability — MECE validation and lifecycle precondition gate checks."""

from __future__ import annotations

from planning.mece_validator import MeceReport, MeceViolation, validate_mece
from planning.preconditions import (
    GateCheckResult,
    PlanningGateError,
    check_enter_analysis,
    check_enter_governance,
    check_enter_planning,
    check_enter_reporting,
)

__all__ = [
    "GateCheckResult",
    "MeceReport",
    "MeceViolation",
    "PlanningGateError",
    "check_enter_analysis",
    "check_enter_governance",
    "check_enter_planning",
    "check_enter_reporting",
    "validate_mece",
]
