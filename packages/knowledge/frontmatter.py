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

S1 is the validator core: it fully validates the common header for every note
and the ADR-004 §3 attribute set for ``framework`` notes. Per-type field models
for the other 12 types are additive in later slices; until then their typed
fields are permitted but not validated (``extra="allow"``).
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


#: Per-type model dispatch. Types absent here validate against the common header
#: only (their typed-field models are additive in later slices).
MODEL_BY_TYPE: dict[str, type[CommonHeader]] = {NoteType.FRAMEWORK.value: FrameworkNote}
