"""Evidence and Assumption ledger record models (ADR-002 §9, §14).

M1.1 scope: **record-level** validation only. Per-evidence-type field requirements
are enforced through a small rule registry (``_EVIDENCE_RULES``) so a new evidence
type can be supported by registering a rule — the model validator stays a thin
dispatcher rather than growing into a monolithic conditional.

Refactored in M1.2 onto ``DomainObject`` (immutable id + optional audit metadata)
and the shared ``ConfidenceScore`` value object; record-level behavior is unchanged.
Aggregate rules, referential integrity, projection, persistence, and events remain
out of scope (later M1 sub-milestones).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from enum import StrEnum

from pydantic import Field, model_validator

from common.models import DomainObject
from common.values import ConfidenceScore
from state.identifiers import (
    AssumptionId,
    EvidenceId,
    new_assumption_id,
    new_evidence_id,
)


class EvidenceType(StrEnum):
    """The four legal origins of a claim (ADR-002 §14)."""

    CLIENT_FACT = "client_fact"
    EXTERNAL_SOURCE = "external_source"
    COMPUTED = "computed"
    ASSUMPTION = "assumption"


class AssumptionStatus(StrEnum):
    """Lifecycle of an assumption (ADR-002 §9)."""

    ACTIVE = "active"
    INVALIDATED = "invalidated"
    CONFIRMED = "confirmed"


class Evidence(DomainObject):
    """A single evidence record (ADR-002 §14).

    ``type`` determines which fields are required; those requirements are enforced
    by the modular rule registry defined below, not by inline conditionals.
    """

    id: EvidenceId = Field(default_factory=new_evidence_id, frozen=True)
    claim: str
    type: EvidenceType
    source: str | None = None
    method: str | None = None
    as_of: datetime | None = None
    confidence: ConfidenceScore
    validated: bool = False
    validator: str | None = None

    @model_validator(mode="after")
    def _enforce_type_requirements(self) -> Evidence:
        _validate_evidence_type(self)
        return self


# --- Modular per-type evidence rules ----------------------------------------
# To add an evidence type: add it to ``EvidenceType`` and, if it has a required
# field, register a rule in ``_EVIDENCE_RULES``. The model validator is untouched.

EvidenceRule = Callable[[Evidence], None]


def _require_source(evidence: Evidence) -> None:
    if not evidence.source:
        raise ValueError(f"evidence of type '{evidence.type.value}' requires 'source'")


def _require_method(evidence: Evidence) -> None:
    if not evidence.method:
        raise ValueError("evidence of type 'computed' requires 'method'")


_EVIDENCE_RULES: dict[EvidenceType, EvidenceRule] = {
    EvidenceType.EXTERNAL_SOURCE: _require_source,  # a citation
    EvidenceType.ASSUMPTION: _require_source,  # a ref to the Assumption
    EvidenceType.COMPUTED: _require_method,  # formula + inputs
    # EvidenceType.CLIENT_FACT: no additional required field.
}


def _validate_evidence_type(evidence: Evidence) -> None:
    rule = _EVIDENCE_RULES.get(evidence.type)
    if rule is not None:
        rule(evidence)


class Assumption(DomainObject):
    """A single assumption ledger record (ADR-002 §9)."""

    id: AssumptionId = Field(default_factory=new_assumption_id, frozen=True)
    statement: str
    value: str
    rationale: str
    owner: str
    confidence: ConfidenceScore
    load_bearing: bool = False
    breakeven: str | None = None
    status: AssumptionStatus = AssumptionStatus.ACTIVE

    @model_validator(mode="after")
    def _enforce_breakeven(self) -> Assumption:
        if self.load_bearing and not self.breakeven:
            raise ValueError("a load-bearing assumption requires 'breakeven'")
        return self
