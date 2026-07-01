"""Engagement State root aggregate (ADR-002).

M1.2 composes all sections (§3–§25) into ``EngagementState``. A newly created state
is valid with only ``metadata`` (plus the default ``status``); every other section
begins ``None`` or as an empty collection and is populated over the engagement
lifecycle. Events, projection, invariants, and persistence are later M1
sub-milestones.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import Field

from core.base import StratAgentModel
from state.enums import LifecycleStatus
from state.identifiers import EngagementId
from state.ledgers import Assumption, Evidence
from state.sections.analysis import AnalysisBlock
from state.sections.governance import ChallengeNotes, ReviewerNotes
from state.sections.output import (
    ConfidenceReport,
    Deliverable,
    KnowledgeLink,
    Recommendations,
)
from state.sections.planning import (
    EngagementPlan,
    FrameworkSelection,
    IssueNode,
    KnowledgeReference,
)
from state.sections.scoping import (
    CaseClassification,
    Constraint,
    Gap,
    Objective,
    ProblemDefinition,
    Stakeholder,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class EngagementMetadata(StratAgentModel):
    """ADR-002 §1 — Engagement Metadata."""

    engagement_id: EngagementId
    tenant_id: str
    slug: str
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
    created_by: Literal["human", "system"] = "human"
    state_version: int = 0
    schema_version: int = 1


class EngagementState(StratAgentModel):
    """Root Engagement State — the single source of truth (ADR-002).

    Valid with only ``metadata``; all other sections default to empty/None and are
    filled over the lifecycle.
    """

    metadata: EngagementMetadata
    status: LifecycleStatus = LifecycleStatus.INTAKE

    # Scoping (§3–§8)
    problem: ProblemDefinition | None = None
    objectives: list[Objective] = []
    success_criteria: list[str] = []
    constraints: list[Constraint] = []
    stakeholders: list[Stakeholder] = []
    classification: CaseClassification | None = None
    information_gaps: list[Gap] = []

    # Ledgers (§9, §14)
    assumptions: list[Assumption] = []
    evidence: list[Evidence] = []

    # Planning (§10–§13)
    plan: EngagementPlan | None = None
    frameworks: list[FrameworkSelection] = []
    issue_tree: list[IssueNode] = []
    knowledge_references: list[KnowledgeReference] = []

    # Analysis (§15–§19)
    financial_analysis: AnalysisBlock | None = None
    market_analysis: AnalysisBlock | None = None
    operations_analysis: AnalysisBlock | None = None
    strategy_analysis: AnalysisBlock | None = None
    risk_analysis: AnalysisBlock | None = None

    # Governance (§20–§21)
    reviewer_notes: ReviewerNotes | None = None
    challenge_notes: ChallengeNotes | None = None

    # Output (§22–§25)
    recommendations: Recommendations | None = None
    confidence: ConfidenceReport | None = None
    deliverables: list[Deliverable] = []
    knowledge_links: list[KnowledgeLink] = []
