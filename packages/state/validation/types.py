"""Validation types: severity, groups, rules, findings, violations, report.

Validators are pure ``EngagementState -> list[Finding]`` functions and know nothing
about rule metadata or each other. The runner attaches rule metadata (id, group,
severity, ADR reference) to each finding to build the ``ValidationReport``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from core.base import StratAgentModel

if TYPE_CHECKING:
    from state.models import EngagementState


class ViolationSeverity(StrEnum):
    """Severity of a rule violation. ERROR/FATAL make a state invalid."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    FATAL = "fatal"


class ValidationGroup(StrEnum):
    """The five rule groups (ADR-002 §Validation Rules)."""

    STRUCTURAL = "structural"
    LIFECYCLE = "lifecycle"
    REFERENTIAL = "referential"
    BUSINESS = "business"
    GOVERNANCE = "governance"


@dataclass(frozen=True)
class Finding:
    """A single problem a validator found — rule-agnostic (no rule id/severity)."""

    path: str
    message: str
    object_id: str | None = None


Validator = Callable[["EngagementState"], list[Finding]]


@dataclass(frozen=True)
class ValidationRule:
    """A first-class validation rule: metadata + its (independent) validator.

    ``rule_id`` values are frozen — never reused or renumbered (see the traceability
    doc). Deprecate a rule by removing it; never recycle its id.
    """

    rule_id: str
    group: ValidationGroup
    severity: ViolationSeverity
    adr_reference: str
    description: str
    validator: Validator


class Violation(StratAgentModel):
    """A rule violation carrying full context (adjustment 8)."""

    rule_id: str
    group: ValidationGroup
    severity: ViolationSeverity
    path: str
    message: str
    object_id: str | None = None


class ValidationReport(StratAgentModel):
    """The result of validating a state."""

    valid: bool
    violations: list[Violation]
    counts: dict[ViolationSeverity, int]
    duration_ms: float
    groups_checked: list[ValidationGroup]
