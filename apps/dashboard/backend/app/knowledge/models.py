"""Core data types for the Consulting Knowledge & Framework Library.

Sits BESIDE ``app.consulting`` (the Workflow Engine) as a peer library it
consumes — never a new orchestration layer. Plain, frozen dataclasses/enums
here, no behavior, the same "models are data" split every layer in this
codebase already uses.

**"No hardcoded execution logic"** is a structural property of this module:
``FrameworkDefinition`` carries only DATA — strings, tuples, small descriptor
dataclasses (``ConfidenceModel``, ``DecisionRule``) — never a callable, never
a code path specific to one framework. Contrast with
``app.consulting.workflow.QualityGate.check``, which DOES hold a callable,
because that callable is GENERIC (the same function class serves every
category) — see ``app.knowledge.quality`` for the equivalent here: generic
checks driven by a framework's declared metadata, never framework-specific
code.

Reuses ``app.consulting.models.EngagementCategory`` for
``supported_engagements`` rather than inventing a parallel taxonomy — the
concrete form of "do not duplicate knowledge already present."
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum

from app.consulting.models import EngagementCategory


class FrameworkCategory(StrEnum):
    STRATEGY = "strategy"
    MARKET_GROWTH = "market_growth"
    OPERATIONS = "operations"
    FINANCE = "finance"
    PRODUCT = "product"
    INNOVATION = "innovation"
    ORGANIZATION = "organization"
    DIGITAL_AI = "digital_ai"
    RISK = "risk"


class CompanySize(StrEnum):
    STARTUP = "startup"
    SMB = "smb"
    MIDMARKET = "midmarket"
    ENTERPRISE = "enterprise"


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


# ---- Framework model sub-structures ----------------------------------------


@dataclass(frozen=True)
class OutputSchema:
    """What a framework execution produces — field NAMES and descriptions,
    never the values (those come from ``execution.py`` at run time)."""

    fields: tuple[str, ...]
    description: str = ""


@dataclass(frozen=True)
class DecisionRule:
    """A declarative, human/agent-readable interpretive rule — descriptive
    text, never a callable. E.g. "score >= 4/5 on 3+ forces -> unattractive
    industry". The judgment of APPLYING it belongs to the analyst/agent using
    this framework; this dataclass only records what the rule IS."""

    id: str
    description: str


@dataclass(frozen=True)
class ConfidenceModel:
    """How confidence in this framework's output should be derived — a
    descriptor, not a formula implementation. ``execution.py``'s generic
    engine reads ``inputs``/``method`` to compute a confidence score from
    whatever the caller actually supplied; see ``quality.py``."""

    method: str  # e.g. "evidence_weighted", "data_completeness", "expert_judgment"
    inputs: tuple[str, ...] = ()
    min_threshold: float = 0.5


@dataclass(frozen=True)
class FrameworkQualityGate:
    """One named completion check a framework declares — mirrors
    ``app.consulting.workflow.QualityGate``'s shape, but ``check_kind`` picks
    one of the GENERIC, reusable checks in ``quality.py`` rather than holding
    a framework-specific callable."""

    id: str
    check_kind: str  # key into quality._CHECKS — see quality.py
    description: str
    mandatory: bool = True


@dataclass(frozen=True)
class FrameworkDefinition:
    """Every field the requester's "Framework Model" + "Design Principles"
    sections named, union'd. Immutable — a catalog entry, never mutated after
    registration (new content -> new version, per "Knowledge Versioning")."""

    id: str
    name: str
    category: FrameworkCategory
    version: str
    description: str
    purpose: str
    when_to_use: tuple[str, ...]
    when_not_to_use: tuple[str, ...]
    required_inputs: tuple[str, ...]
    optional_inputs: tuple[str, ...] = ()
    required_evidence: tuple[str, ...] = ()
    output_schema: OutputSchema = field(default_factory=lambda: OutputSchema(fields=()))
    quality_gates: tuple[FrameworkQualityGate, ...] = ()
    decision_rules: tuple[DecisionRule, ...] = ()
    assumptions: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()  # other framework ids (composition order)
    confidence_model: ConfidenceModel = field(
        default_factory=lambda: ConfidenceModel(method="evidence_weighted")
    )
    supported_engagements: tuple[EngagementCategory, ...] = ()
    supported_industries: tuple[str, ...] = ("all",)
    supported_company_sizes: tuple[CompanySize, ...] = (
        CompanySize.STARTUP,
        CompanySize.SMB,
        CompanySize.MIDMARKET,
        CompanySize.ENTERPRISE,
    )
    estimated_duration_days: float = 2.0
    owner: str = "StratAgent Knowledge Library"
    tags: tuple[str, ...] = ()
    deprecated: bool = False
    replaced_by: str | None = None


# ---- Execution ---------------------------------------------------------------


@dataclass(frozen=True)
class FrameworkExecutionRequest:
    """What a caller (an analyst agent) supplies to execute a framework.

    Every analytical field here (``questions``/``analyses``/``calculations``/
    ``findings``/``confidence``/``recommendations``/``limitations``/
    ``next_analyses``) is CALLER-supplied — the concrete meaning of "no
    hardcoded execution logic": this library validates and packages, it never
    computes the analysis content itself.
    """

    provided_inputs: tuple[str, ...] = ()
    provided_evidence: tuple[str, ...] = ()
    completed_dependency_ids: tuple[str, ...] = ()
    questions: tuple[str, ...] = ()
    analyses: tuple[str, ...] = ()
    calculations: dict = field(default_factory=dict)
    findings: tuple[str, ...] = ()
    confidence: float | None = None
    recommendations: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    next_analyses: tuple[str, ...] = ()
    calculations_verified: bool = False


@dataclass(frozen=True)
class FrameworkExecutionResult:
    """Structured execution output (requester's "Framework Execution"
    section). Deliberately NOT a recommendation — ``recommendations`` here
    are framework-level analytical implications ("this force is a major
    threat"), never an engagement-level executive recommendation (that is
    ``app.consulting.tracking.create_recommendation``'s job, downstream)."""

    id: str
    framework_id: str
    framework_version: str
    questions: tuple[str, ...]
    analyses: tuple[str, ...]
    calculations: dict
    findings: tuple[str, ...]
    confidence: float
    recommendations: tuple[str, ...]
    limitations: tuple[str, ...]
    next_analyses: tuple[str, ...]
    quality_gate_results: tuple  # tuple[FrameworkQualityGateResult, ...]
    success: bool
    error: str | None = None
    executed_at: float = field(default_factory=time.time)


def new_execution_id() -> str:
    return _new_id("fexec")


@dataclass(frozen=True)
class FrameworkQualityGateCheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class FrameworkQualityGateResult:
    gate_id: str
    mandatory: bool
    passed: bool
    checks: tuple[FrameworkQualityGateCheckResult, ...]


# ---- Selection -----------------------------------------------------------


@dataclass(frozen=True)
class SelectionContext:
    """Every input the requester's "Framework Selection" section named."""

    engagement_type: EngagementCategory
    industry: str = "all"
    business_problem: str = ""
    available_data: tuple[str, ...] = ()
    available_evidence: tuple[str, ...] = ()
    company_size: CompanySize = CompanySize.MIDMARKET
    workflow_stage: str = ""
    confidence: float = 0.5


@dataclass(frozen=True)
class FrameworkRecommendation:
    framework_id: str
    priority: int  # 1 = highest
    reasoning: tuple[str, ...]
    confidence: float


@dataclass(frozen=True)
class SelectionResult:
    recommended: tuple[FrameworkRecommendation, ...]
    alternatives: tuple[FrameworkRecommendation, ...]


# ---- Composition -----------------------------------------------------------


@dataclass(frozen=True)
class CompositionIssue:
    framework_id: str
    reason: str


@dataclass(frozen=True)
class CompositionPlan:
    """A validated, ordered sequence of frameworks — the requester's Market
    Entry example (PESTLE -> Five Forces -> TAM/SAM/SOM -> SWOT -> Financial
    Model -> Risk Matrix)."""

    execution_order: tuple[str, ...]
    valid: bool
    issues: tuple[CompositionIssue, ...] = ()


# ---- Versioning --------------------------------------------------------------


@dataclass(frozen=True)
class DeprecationInfo:
    framework_id: str
    version: str
    replaced_by: str | None
    reason: str
    deprecated_at: float = field(default_factory=time.time)


@dataclass(frozen=True)
class ExecutionHistoryEntry:
    execution_id: str
    framework_id: str
    framework_version: str
    success: bool
    confidence: float
    executed_at: float
