"""Knowledge-note frontmatter schema (M2-S1).

Typed models for the YAML frontmatter every ``knowledge-vault/`` note carries.
The schema is derived directly from the governing ADRs and cites them:

- **Common header** — ADR-003 §5 "Note Metadata Schema" (all notes).
- **Required governance fields** — ADR-003 §10: ``source`` (provenance),
  ``visibility``/``tenant`` (isolation), ``last_verified`` (freshness); plus
  ``status`` ∈ {approved, draft} (Roadmap M2 exit).
- **Note types** — ADR-003 §5 enum (8) ∪ ADR-004 types (5) = 13.
- **Framework note** — ADR-004 §3 "framework asset schema" **governs** (decision
  D-7): the 11 required framework attributes, superseding ADR-003 §5's smaller
  framework field list.

S1 provided the common header + the ADR-004 §3 ``framework`` model. S2 adds a
model for **every** note type. Requiredness is enforced **only where an ADR
states it** (``framework`` §3); the ADR-003 §5 per-type fields are typed but
**optional** (the ADRs do not mark them required), and the five ADR-004-added
types (``domain``/``issue_tree``/``deliverable``/``business_problem``/
``recommendation``) have **no** frontmatter field schema in the ADRs — only
content/graph definitions — so they validate at the common-header level (see
decision D-8). ``extra="allow"`` throughout keeps un-modelled fields permitted.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from common.errors import StratAgentError


class FrontmatterError(StratAgentError):
    """A note's frontmatter is missing, malformed, or fails the schema."""


class NoteType(StrEnum):
    """The knowledge note types — ADR-003 §5 (8) plus ADR-004 additions (5)."""

    # ADR-003 §5
    FRAMEWORK = "framework"
    PLAYBOOK = "playbook"
    INDUSTRY = "industry"
    COMPANY = "company"
    KPI = "kpi"
    PRIOR_CASE = "prior_case"
    LESSON = "lesson"
    TEMPLATE = "template"
    # ADR-004 (added to the ADR-003 §5 schema)
    DOMAIN = "domain"
    ISSUE_TREE = "issue_tree"
    DELIVERABLE = "deliverable"
    BUSINESS_PROBLEM = "business_problem"
    RECOMMENDATION = "recommendation"


class NoteStatus(StrEnum):
    """Governance status — Roadmap M2: every note is ``approved`` or ``draft``."""

    APPROVED = "approved"
    DRAFT = "draft"


class Visibility(StrEnum):
    """Tenant-isolation scope — ADR-003 §5/§10."""

    GLOBAL = "global"
    TENANT = "tenant"


class FrameworkTier(StrEnum):
    """Framework tier within a domain — ADR-004 §3."""

    PRIMARY = "primary"
    SUPPORTING = "supporting"


class DeliverableKind(StrEnum):
    """Template deliverable kind — ADR-003 §5 ``template``."""

    REPORT = "report"
    DECK = "deck"
    MODEL = "model"


class CommonHeader(BaseModel):
    """The frontmatter header carried by **every** note (ADR-003 §5 + §10).

    ``extra="allow"`` so a note's per-type fields (validated by a subclass, or
    deferred to a later slice) do not fail common-header validation.
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    # structural identity (ADR-003 §5 / §8: `id` node identity, `type` node label)
    id: str = Field(min_length=1)
    type: NoteType
    title: str = Field(min_length=1)
    # governance — required (ADR-003 §10 + Roadmap M2)
    source: str = Field(min_length=1)  # provenance required (§10)
    last_verified: date  # freshness (§10)
    status: NoteStatus  # approved | draft (Roadmap M2)
    visibility: Visibility  # on every note (§10)
    tenant: str | None = None  # required iff visibility == tenant (§5)
    # optional common fields (ADR-003 §5)
    tags: list[str] = []
    created: date | None = None
    updated: date | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    aliases: list[str] = []

    @model_validator(mode="after")
    def _check_tenant_isolation(self) -> Self:
        if self.visibility is Visibility.TENANT and not self.tenant:
            raise ValueError("visibility=tenant requires a non-empty 'tenant'")
        if self.visibility is Visibility.GLOBAL and self.tenant:
            raise ValueError("visibility=global must not set 'tenant'")
        return self


class FrameworkNote(CommonHeader):
    """A ``framework`` note — ADR-004 §3 asset schema (decision D-7: §3 governs).

    The 11 required framework attributes beyond the common header. Content lists
    are required non-empty (the schema is "tight by design", ADR-004 §3);
    ``related_frameworks`` is required-present but may be empty (a foundational
    framework need not reference another).
    """

    name: str = Field(min_length=1)
    domains: list[str] = Field(min_length=1)  # domain refs
    tier: FrameworkTier
    purpose: str = Field(min_length=1)
    when_to_use: str = Field(min_length=1)
    diagnostic_questions: list[str] = Field(min_length=1)
    success_metrics: list[str] = Field(min_length=1)  # KPI refs
    common_risks: list[str] = Field(min_length=1)
    common_mistakes: list[str] = Field(min_length=1)
    related_frameworks: list[str]  # required-present, may be empty
    version: str = Field(min_length=1)


# --- ADR-003 §5 per-type models (fields typed but OPTIONAL — the ADR does not
#     mark them required; only `framework` (ADR-004 §3) has a required schema). --


class PlaybookNote(CommonHeader):
    """ADR-003 §5 ``playbook``."""

    industry: str | None = None  # ref
    applies_to_archetypes: list[str] = []
    kpis: list[str] = []  # refs
    plays: list[str] = []


class IndustryNote(CommonHeader):
    """ADR-003 §5 ``industry`` (+ ADR-004 §6 content model)."""

    structure: str | None = None
    typical_margins: str | None = None
    growth_rate: str | None = None
    key_kpis: list[str] = []  # refs


class CompanyNote(CommonHeader):
    """ADR-003 §5 ``company``."""

    industry: str | None = None  # ref
    size: str | None = None
    geo: str | None = None
    segments: list[str] = []
    kpis: list[str] = []  # refs


class KpiNote(CommonHeader):
    """ADR-003 §5 ``kpi`` (+ ADR-004 §5 KPI library)."""

    formula: str | None = None
    unit: str | None = None
    benchmark: str | None = None
    industry: str | None = None  # ref


class PriorCaseNote(CommonHeader):
    """ADR-003 §5 ``prior_case``."""

    archetype: str | None = None
    client_anon: str | None = None
    frameworks: list[str] = []  # refs
    recommendation: str | None = None
    outcome: str | None = None


class LessonNote(CommonHeader):
    """ADR-003 §5 ``lesson``."""

    applies_to: str | None = None
    framework_ref: str | None = None  # ref
    source_engagement: str | None = None


class TemplateNote(CommonHeader):
    """ADR-003 §5 ``template`` — the one enum-typed per-type field."""

    deliverable_kind: DeliverableKind | None = None


# --- ADR-004-added types: no frontmatter field schema in the ADRs (D-8) —
#     validated at the common-header level. A few clearly-inferred optional
#     fields are typed where a section implies them; nothing is required. -------


class DomainNote(CommonHeader):
    """ADR-004 §2 ``domain`` — content only in the ADR; header-level validation."""


class IssueTreeNote(CommonHeader):
    """ADR-004 §4 ``issue_tree`` — instantiates one or more frameworks (§4)."""

    frameworks: list[str] = []  # refs (§4: "instantiate one or more frameworks")


class DeliverableNote(CommonHeader):
    """ADR-004 §7 ``deliverable`` — content only in the ADR; header-level."""


class BusinessProblemNote(CommonHeader):
    """ADR-004 §8 ``business_problem`` — graph only in the ADR; header-level."""


class RecommendationNote(CommonHeader):
    """ADR-004 §8 ``recommendation`` — graph only in the ADR; header-level."""


#: Per-type model dispatch — a model for **every** note type (S2). Unmodelled
#: fields are permitted (``extra="allow"``); requiredness is enforced only where
#: an ADR states it.
MODEL_BY_TYPE: dict[str, type[CommonHeader]] = {
    NoteType.FRAMEWORK.value: FrameworkNote,
    NoteType.PLAYBOOK.value: PlaybookNote,
    NoteType.INDUSTRY.value: IndustryNote,
    NoteType.COMPANY.value: CompanyNote,
    NoteType.KPI.value: KpiNote,
    NoteType.PRIOR_CASE.value: PriorCaseNote,
    NoteType.LESSON.value: LessonNote,
    NoteType.TEMPLATE.value: TemplateNote,
    NoteType.DOMAIN.value: DomainNote,
    NoteType.ISSUE_TREE.value: IssueTreeNote,
    NoteType.DELIVERABLE.value: DeliverableNote,
    NoteType.BUSINESS_PROBLEM.value: BusinessProblemNote,
    NoteType.RECOMMENDATION.value: RecommendationNote,
}
