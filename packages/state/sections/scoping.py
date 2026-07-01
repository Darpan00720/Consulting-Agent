"""Scoping-phase section models (ADR-002 §3–§8)."""

from __future__ import annotations

from datetime import datetime

from common.models import DomainObject
from common.values import ConfidenceScore, Reference
from state.sections.enums import (
    CaseArchetype,
    ConstraintType,
    GapCriticality,
    GapStatus,
    ObjectiveSource,
    StakeholderRelationship,
)


class Document(DomainObject):
    """An ingested client document (ADR-002 §3)."""

    path: str
    kind: str | None = None
    ingested_at: datetime | None = None
    screened: bool = False


class ProblemDefinition(DomainObject):
    """ADR-002 §3 — Problem Definition."""

    raw_input: str
    documents: list[Document] = []
    real_question: str | None = None
    restated_at: datetime | None = None


class Objective(DomainObject):
    """ADR-002 §4 — a single objective."""

    statement: str
    metric: str | None = None
    target: str | None = None
    priority: int | None = None
    source: ObjectiveSource | None = None


class Constraint(DomainObject):
    """ADR-002 §5 — a single constraint."""

    statement: str
    type: ConstraintType = ConstraintType.OTHER
    hard: bool = True


class Stakeholder(DomainObject):
    """ADR-002 §6 — a single stakeholder."""

    name_or_role: str
    relationship: StakeholderRelationship = StakeholderRelationship.OTHER
    interest: str | None = None


class CaseClassification(DomainObject):
    """ADR-002 §7 — Case Classification."""

    primary_archetype: CaseArchetype
    secondary_archetype: CaseArchetype | None = None
    confidence: ConfidenceScore
    rationale: str | None = None


class Gap(DomainObject):
    """ADR-002 §8 — a single information gap."""

    question: str
    criticality: GapCriticality = GapCriticality.USEFUL
    status: GapStatus = GapStatus.OPEN
    resolution: str | None = None
    assumption_ref: Reference | None = None
