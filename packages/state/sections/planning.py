"""Planning-phase section models (ADR-002 §10–§13)."""

from __future__ import annotations

from datetime import datetime

from common.models import DomainObject
from common.values import ConfidenceScore, Reference
from state.sections.enums import (
    CaseArchetype,
    IssueNodeStatus,
    KnowledgeRefKind,
    PlanStepStatus,
)


class PlanStep(DomainObject):
    """A single step in the engagement plan (ADR-002 §10)."""

    description: str
    agent: str | None = None
    depends_on: list[Reference] = []
    status: PlanStepStatus = PlanStepStatus.PENDING


class EngagementPlan(DomainObject):
    """ADR-002 §10 — Engagement Plan."""

    steps: list[PlanStep] = []
    parallel_groups: list[list[Reference]] = []
    replans: int = 0


class FrameworkSelection(DomainObject):
    """ADR-002 §11 — a selected and adapted framework."""

    name: str
    archetype: CaseArchetype | None = None
    rationale: str | None = None
    adaptation: str | None = None
    source_ref: Reference | None = None


class IssueNode(DomainObject):
    """ADR-002 §12 — a node in the (flat, parent-referenced) issue tree."""

    parent: Reference | None = None
    question: str
    owner: str | None = None
    status: IssueNodeStatus = IssueNodeStatus.OPEN
    answer: str | None = None
    confidence: ConfidenceScore | None = None
    evidence_refs: list[Reference] = []


class KnowledgeReference(DomainObject):
    """ADR-002 §13 — an inbound knowledge-retrieval reference."""

    kind: KnowledgeRefKind
    vault_path: str | None = None
    graph_node: str | None = None
    query: str | None = None
    relevance: ConfidenceScore | None = None
    retrieved_at: datetime | None = None
