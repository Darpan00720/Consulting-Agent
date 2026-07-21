"""Core data types for the Client Deliverables & Presentation Engine.

Sits BESIDE ``app.consulting`` (methodology), ``app.knowledge`` (frameworks),
``app.organization`` (roles), and ``app.synthesis`` (reasoning) as a fifth
peer library: this package answers how APPROVED synthesis outputs become a
client-ready deliverable. It performs no consulting reasoning of its own —
every generated section's content is a reference to, or a direct copy of,
real ``app.synthesis`` content, never invented.

Reuses ``app.consulting.models.EngagementCategory`` and
``app.organization.models.DecisionType`` rather than inventing parallel
taxonomies — "do not duplicate" applied a fourth time.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum

from app.consulting.models import EngagementCategory
from app.organization.models import DecisionType


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


# ---- Deliverable taxonomy (requester's "Deliverable Types" section) -------


class DeliverableType(StrEnum):
    EXECUTIVE_SUMMARY = "executive_summary"
    BOARD_PRESENTATION = "board_presentation"
    STRATEGY_MEMORANDUM = "strategy_memorandum"
    BUSINESS_CASE = "business_case"
    MARKET_ENTRY_REPORT = "market_entry_report"
    TRANSFORMATION_ROADMAP = "transformation_roadmap"
    DIGITAL_TRANSFORMATION_STRATEGY = "digital_transformation_strategy"
    AI_STRATEGY_REPORT = "ai_strategy_report"
    OPERATIONAL_EXCELLENCE_REPORT = "operational_excellence_report"
    DUE_DILIGENCE_REPORT = "due_diligence_report"
    IMPLEMENTATION_ROADMAP = "implementation_roadmap"
    PMO_STATUS_REPORT = "pmo_status_report"
    RISK_ASSESSMENT_REPORT = "risk_assessment_report"
    EXECUTIVE_BRIEFING = "executive_briefing"
    STEERING_COMMITTEE_DECK = "steering_committee_deck"
    WORKSHOP_PACK = "workshop_pack"
    CLIENT_PROPOSAL = "client_proposal"
    INVESTMENT_COMMITTEE_MEMO = "investment_committee_memo"
    POST_ENGAGEMENT_REPORT = "post_engagement_report"
    LESSONS_LEARNED = "lessons_learned"


class Audience(StrEnum):
    """The requester's "Executive Communication" section, verbatim."""

    CEO = "ceo"
    BOARD = "board"
    CFO = "cfo"
    COO = "coo"
    CTO = "cto"
    CHRO = "chro"
    BUSINESS_UNIT_LEADER = "business_unit_leader"
    PROGRAM_SPONSOR = "program_sponsor"


class ExportFormat(StrEnum):
    POWERPOINT = "powerpoint"
    WORD = "word"
    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"
    PDF = "pdf"


class VisualType(StrEnum):
    """The requester's "Presentation Model" visual list, verbatim."""

    CHART = "chart"
    TABLE = "table"
    FRAMEWORK_VISUAL = "framework_visual"
    ROADMAP = "roadmap"
    MATRIX = "matrix"
    TIMELINE = "timeline"
    DECISION_TREE = "decision_tree"
    RISK_HEATMAP = "risk_heatmap"
    IMPLEMENTATION_WAVE = "implementation_wave"


# ---- Section model (requester's "Section Model" section) ------------------


@dataclass(frozen=True)
class SectionDefinition:
    """One reusable section, shared across deliverable types (the same
    "small library of building blocks composed differently per catalog
    entry" pattern ``app.consulting.workflow.standard_workflow`` and
    ``app.knowledge.catalog`` already established)."""

    id: str
    title: str
    purpose: str
    required_inputs: tuple[str, ...]
    supported_content: tuple[str, ...]
    traceability_references: tuple[str, ...]
    quality_requirements: tuple[str, ...]
    default_order: int
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class GeneratedSection:
    """A section as actually built for one deliverable — real content
    derived from ``app.synthesis``, never invented. ``traced_ids`` names
    every synthesis-chain object (recommendation/finding/insight/narrative
    id) this section's content actually came from."""

    section_id: str
    title: str
    content: tuple[str, ...]
    traced_ids: tuple[str, ...]
    visual_ids: tuple[str, ...] = ()


# ---- Deliverable model (requester's "Deliverable Model" section) ---------


@dataclass(frozen=True)
class DeliverableDefinition:
    """Every field the requester named."""

    id: str
    name: str
    purpose: str
    audience: tuple[Audience, ...]
    template: str
    required_sections: tuple[str, ...]
    optional_sections: tuple[str, ...]
    required_artifacts: tuple[str, ...]
    supported_engagement_types: tuple[EngagementCategory, ...]
    supported_industries: tuple[str, ...]
    required_approvals: tuple[DecisionType, ...]
    quality_checklist: tuple[str, ...]
    version: str = "1.0.0"
    owner: str = "StratAgent Deliverables Engine"
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class GeneratedDeliverable:
    id: str
    deliverable_type: DeliverableType
    audience: Audience
    sections: tuple[GeneratedSection, ...]
    visuals: tuple[VisualSpec, ...]
    quality_report: DeliverableQualityReport | None = None
    created_at: float = field(default_factory=time.time)


def new_deliverable_id() -> str:
    return _new_id("deliv")


# ---- Narrative structure (requester's "Narrative Engine" section) --------


@dataclass(frozen=True)
class NarrativeStructure:
    """Situation-Complication-Resolution, plus the requester's additional
    named sections — assembled FROM a real ``app.synthesis.StrategicNarrative``
    and its referenced recommendations, never invented prose."""

    situation: str
    complication: str
    resolution: str
    business_impact: tuple[str, ...]
    implementation: tuple[str, ...]
    expected_outcomes: tuple[str, ...]
    risks: tuple[str, ...]
    dependencies: tuple[str, ...]
    source_narrative_id: str
    source_recommendation_ids: tuple[str, ...]


# ---- Presentation / visual model -------------------------------------------


@dataclass(frozen=True)
class VisualSpec:
    """A structured visual specification — data only, never a rendered
    image. ``data_refs`` names the real synthesis object ids this visual
    represents; ``data`` is the structured payload a renderer consumes,
    derived FROM those objects, never invented."""

    id: str
    visual_type: VisualType
    title: str
    data_refs: tuple[str, ...]
    data: dict


def new_visual_id() -> str:
    return _new_id("vis")


# ---- Quality model (requester's "Quality Model" section) ------------------
#
# Prefixed ``Deliverable*`` (not bare ``QualityDimension``/``QualityCheckResult``/
# ``QualityReport``) — a 2026-07-19 architecture review found this module had
# reused ``app.synthesis.models``'s exact class names for a structurally
# identical but semantically distinct concept (deliverable-quality dimensions
# vs. synthesis-chain-quality dimensions). Prefixing matches the precedent
# ``app.knowledge.models`` already set (``FrameworkQualityGate*``) for the
# same reason: same word, different altitude, must not collide on import.


class DeliverableQualityDimension(StrEnum):
    TRACEABILITY = "traceability"
    EXECUTIVE_CLARITY = "executive_clarity"
    CONSISTENCY = "consistency"
    SECTION_COMPLETENESS = "section_completeness"
    SUPPORTING_EVIDENCE = "supporting_evidence"
    VISUAL_COMPLETENESS = "visual_completeness"
    AUDIENCE_SUITABILITY = "audience_suitability"
    APPROVAL_STATUS = "approval_status"


@dataclass(frozen=True)
class DeliverableQualityCheckResult:
    dimension: DeliverableQualityDimension
    passed: bool
    score: float
    detail: str = ""


@dataclass(frozen=True)
class DeliverableQualityReport:
    checks: tuple[DeliverableQualityCheckResult, ...]
    overall_score: float

    @property
    def all_passed(self) -> bool:
        return all(c.passed for c in self.checks)


# ---- Export model -----------------------------------------------------------


@dataclass(frozen=True)
class TraceabilityMetadata:
    """Preserved inside every exported artifact regardless of format — the
    requester's "the exported artifact must preserve traceability metadata
    internally" as real, checkable data."""

    deliverable_id: str
    recommendation_ids: tuple[str, ...]
    finding_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    narrative_id: str | None


@dataclass(frozen=True)
class ExportResult:
    format: ExportFormat
    content: bytes
    content_type: str
    traceability: TraceabilityMetadata
    is_placeholder: bool = False
