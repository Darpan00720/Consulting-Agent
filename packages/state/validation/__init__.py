"""Engagement State validation (ADR-002 §Validation Rules).

Rules are grouped (structural, lifecycle, referential, business, governance); each
validator is pure and independent; orchestration lives only in the runner. Rule ids
are a frozen namespace — never reused or renumbered. Internal package (surfaced via
the facade in a later milestone).
"""

from state.validation.runner import (
    ALL_RULES,
    StateValidationError,
    raise_if_invalid,
    validate,
)
from state.validation.types import (
    Finding,
    ValidationGroup,
    ValidationReport,
    ValidationRule,
    Violation,
    ViolationSeverity,
)

__all__ = [
    "ALL_RULES",
    "Finding",
    "StateValidationError",
    "ValidationGroup",
    "ValidationReport",
    "ValidationRule",
    "Violation",
    "ViolationSeverity",
    "raise_if_invalid",
    "validate",
]
