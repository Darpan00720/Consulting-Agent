"""The Workflow model (requester's deliverable 2/3/4): ``WorkflowDefinition``,
``QualityGate``, and ``standard_workflow`` — the builder that lets a new
engagement category register in one call instead of a hand-written class.

**"Do not hardcode workflows. Register them."** ``standard_workflow`` is the
mechanism: every one of the 28 categories the requester listed shares the
same 10-stage lifecycle and the same mandatory quality gates (the elite-firm
methodology doesn't change per category — the frameworks/analyses a category
favors do). A 29th category is a one-line call in ``registry.py``, never a
new class, never a change to ``engine.py`` — the concrete proof behind
"support future engagement types without redesign."
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.consulting.models import (
    STAGE_ORDER,
    ConsultingStage,
    EngagementCategory,
    QualityGateResult,
)

if TYPE_CHECKING:
    from app.consulting.state import EngagementState

GateCheckFn = Callable[["EngagementState"], QualityGateResult]


@dataclass(frozen=True)
class QualityGate:
    """One stage-completion check (requester's "Quality Gates" section).
    ``check`` is a pure function ``EngagementState -> QualityGateResult`` —
    the concrete implementations live in ``quality_gates.py``; this dataclass
    is just the reusable shape a workflow definition references."""

    id: str
    stage: ConsultingStage
    description: str
    mandatory: bool
    check: GateCheckFn


@dataclass(frozen=True)
class WorkflowDefinition:
    """Every field the requester's "Workflow Object" section named."""

    id: str
    name: str
    version: str
    category: EngagementCategory
    required_stages: tuple[ConsultingStage, ...]
    optional_stages: tuple[ConsultingStage, ...] = ()
    entry_criteria: tuple[str, ...] = ()
    exit_criteria: tuple[str, ...] = ()
    required_inputs: tuple[str, ...] = ()
    required_outputs: tuple[str, ...] = ()
    quality_gates: tuple[QualityGate, ...] = ()
    dependencies: tuple[str, ...] = ()
    estimated_effort_days: float = 10.0
    supported_frameworks: tuple[str, ...] = ()
    supported_analyses: tuple[str, ...] = ()
    required_evidence: tuple[str, ...] = ()

    def gates_for(self, stage: ConsultingStage) -> tuple[QualityGate, ...]:
        return tuple(g for g in self.quality_gates if g.stage is stage)


# Category-specific framework/analysis hints — real content, not filler,
# but deliberately data (a dict), not per-category classes, since that is
# exactly what "do not hardcode workflows" rules out.
_FRAMEWORK_HINTS: dict[EngagementCategory, tuple[str, ...]] = {
    EngagementCategory.CORPORATE_STRATEGY: ("Portfolio matrix", "Ansoff matrix"),
    EngagementCategory.BUSINESS_STRATEGY: ("Porter's Five Forces", "SWOT"),
    EngagementCategory.GROWTH_STRATEGY: ("Ansoff matrix", "Growth share matrix"),
    EngagementCategory.MARKET_ENTRY: (
        "Market sizing (TAM/SAM/SOM)",
        "Porter's Five Forces",
    ),
    EngagementCategory.GO_TO_MARKET: ("Segmentation-targeting-positioning", "4Ps"),
    EngagementCategory.PRICING_STRATEGY: ("Van Westendorp", "Value-based pricing"),
    EngagementCategory.PORTFOLIO_STRATEGY: ("BCG matrix", "GE-McKinsey matrix"),
    EngagementCategory.COST_REDUCTION: ("Zero-based budgeting", "Cost-to-serve"),
    EngagementCategory.OPERATIONAL_EXCELLENCE: ("Lean", "Six Sigma"),
    EngagementCategory.PROCESS_OPTIMIZATION: ("Value stream mapping", "Lean"),
    EngagementCategory.SUPPLY_CHAIN: ("SCOR model", "Inventory optimization"),
    EngagementCategory.DIGITAL_TRANSFORMATION: (
        "Digital maturity model",
        "Capability heat map",
    ),
    EngagementCategory.AI_TRANSFORMATION: (
        "AI maturity model",
        "Use-case prioritization matrix",
    ),
    EngagementCategory.AUTOMATION_STRATEGY: (
        "Process automation matrix",
        "RPA feasibility",
    ),
    EngagementCategory.TECHNOLOGY_MODERNIZATION: ("TIME model", "Tech debt quadrant"),
    EngagementCategory.ORGANIZATIONAL_DESIGN: (
        "McKinsey 7S",
        "Span-of-control analysis",
    ),
    EngagementCategory.WORKFORCE_STRATEGY: (
        "Workforce planning model",
        "Skills gap analysis",
    ),
    EngagementCategory.CHANGE_MANAGEMENT: ("Kotter's 8-step", "ADKAR"),
    EngagementCategory.INVESTMENT_EVALUATION: ("NPV/IRR", "Real options"),
    EngagementCategory.BUSINESS_CASE: ("Cost-benefit analysis", "Sensitivity analysis"),
    EngagementCategory.DUE_DILIGENCE: ("Commercial due diligence", "Synergy sizing"),
    EngagementCategory.FINANCIAL_PERFORMANCE: ("DuPont analysis", "P&L bridge"),
    EngagementCategory.PRODUCT_STRATEGY: ("Kano model", "Product-market fit canvas"),
    EngagementCategory.INNOVATION_STRATEGY: (
        "Three Horizons",
        "Innovation ambition matrix",
    ),
    EngagementCategory.VENTURE_VALIDATION: ("Lean canvas", "Jobs-to-be-done"),
    EngagementCategory.RISK_ASSESSMENT: ("Risk register (likelihood x impact)", "FMEA"),
    EngagementCategory.SCENARIO_PLANNING: ("Scenario matrix", "Monte Carlo"),
    EngagementCategory.BUSINESS_CONTINUITY: (
        "BIA (business impact analysis)",
        "Resilience matrix",
    ),
}


def standard_workflow(
    category: EngagementCategory,
    *,
    quality_gates: tuple[QualityGate, ...],
    version: str = "1.0.0",
    optional_stages: tuple[ConsultingStage, ...] = (),
    estimated_effort_days: float = 10.0,
) -> WorkflowDefinition:
    """Build a standardized, full-lifecycle workflow for one category. The
    SAME 10-stage methodology and the SAME quality-gate set apply to every
    category — this is the concrete mechanism satisfying "do not hardcode
    workflows; register them" and "support future engagement types without
    redesign": adding category N+1 is one call to this function."""
    return WorkflowDefinition(
        id=f"workflow.{category.value}",
        name=category.value.replace("_", " ").title(),
        version=version,
        category=category,
        required_stages=STAGE_ORDER,
        optional_stages=optional_stages,
        entry_criteria=("engagement scope confirmed with client stakeholder",),
        exit_criteria=("executive deliverable generated and internally consistent",),
        required_inputs=("problem statement", "stakeholder list"),
        required_outputs=(
            "executive summary",
            "recommendation matrix",
            "implementation roadmap",
        ),
        quality_gates=quality_gates,
        dependencies=(),
        estimated_effort_days=estimated_effort_days,
        supported_frameworks=_FRAMEWORK_HINTS.get(category, ()),
        supported_analyses=("hypothesis-driven analysis", "evidence synthesis"),
        required_evidence=("internal_memory", "knowledge_library"),
    )
