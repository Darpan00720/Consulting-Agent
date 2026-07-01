"""Output-phase section models (ADR-002 §22–§25)."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from common.models import DomainObject
from common.values import ConfidenceScore, Reference
from state.identifiers import (
    DeliverableId,
    RecommendationId,
    new_deliverable_id,
    new_recommendation_id,
)
from state.sections.enums import (
    DeliverableKind,
    DeliverableStatus,
    RecommendationStatus,
)


class NextStep(DomainObject):
    """A single implementation next-step (ADR-002 §22)."""

    step: str
    sequence: int | None = None
    depends_on: list[Reference] = []


class RejectedAlternative(DomainObject):
    """A considered-but-rejected option (ADR-002 §22)."""

    option: str
    why_not: str | None = None


class Recommendations(DomainObject):
    """ADR-002 §22 — Recommendations."""

    id: RecommendationId = Field(default_factory=new_recommendation_id, frozen=True)
    decision: str | None = None
    rationale: str | None = None
    next_steps: list[NextStep] = []
    risks: list[str] = []
    alternatives_rejected: list[RejectedAlternative] = []
    status: RecommendationStatus = RecommendationStatus.DRAFT


class ConfidenceReport(DomainObject):
    """ADR-002 §23 — Confidence Scores (rollup)."""

    by_section: dict[str, ConfidenceScore] = {}
    overall: ConfidenceScore | None = None
    method: str | None = None
    drivers: list[str] = []


class Deliverable(DomainObject):
    """ADR-002 §24 — a single deliverable."""

    id: DeliverableId = Field(default_factory=new_deliverable_id, frozen=True)
    kind: DeliverableKind
    path: str | None = None
    format: str | None = None
    status: DeliverableStatus = DeliverableStatus.PENDING
    generated_at: datetime | None = None


class KnowledgeLink(DomainObject):
    """ADR-002 §25 — an outbound knowledge-graph link."""

    graph_node: str | None = None
    relationship: str | None = None
    vault_note: str | None = None
    tenant_id: str | None = None
