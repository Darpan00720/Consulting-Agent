"""Consulting Intelligence Layer — typed contracts (ADR-010 Phase 3).

These are the machine-checkable shapes for the consulting-judgment artifacts a
real engagement produces: the problem statement, the issue tree, hypotheses,
research assignments, strategic options, and the recommendations derived from
them. They exist so Governance (P4) can consume STRUCTURE, never prose — the
same reason ``evidence_schema.py`` exists for analyst findings (P2).

What this module does NOT do: generate any of these. There is no algorithm
that produces "the MECE issue tree" for an arbitrary business problem — that
is consulting judgment, and judgment is the LLM's job (see ADR-010 §6b for the
full reasoning). This module only defines the contract an LLM's output must
satisfy, and (like ``evidence_schema.py``) a strict parser that validates it.
`consulting_validators.py` is the deterministic layer that checks COMPLETENESS
against these contracts (MECE structure, hypothesis evidence-linkage,
research coverage) — still never generating, only checking.

Versioned (``SCHEMA_VERSION``) for the same reason as evidence atoms: a v2
contract adds fields without invalidating v1 data already in flight.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal

SCHEMA_VERSION = 1

_SLUG_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")

RISK_TOLERANCE = ("low", "medium", "high")
HYPOTHESIS_STATUSES = ("untested", "supported", "contradicted", "retired")
DEPENDENCY_TYPES = (
    "technology",
    "budget",
    "people",
    "regulatory",
    "data",
    "vendor",
    "change_management",
    "timeline",
)
CAPABILITY_CATEGORIES = (
    "organization",
    "technology",
    "people",
    "budget",
    "timeline",
    "governance",
    "skills",
    "operating_model",
)


class SchemaError(ValueError):
    """A contract object failed validation. Message is exact and actionable,
    matching the style of every other validator in this pipeline."""


def _require_slug(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not _SLUG_RE.match(value):
        raise SchemaError(
            f"{field_name} must be a slug (letters/digits/underscore, "
            f"starting with a letter), got {value!r}."
        )
    return value


# --- Case Definition ----------------------------------------------------------


@dataclass(frozen=True)
class CaseDefinition:
    """Structured extraction of a raw case prompt: what the client wants,
    what's known, and what bounds the decision — the input every downstream
    consulting artifact (issue tree, hypotheses, research plan) is scoped by.
    """

    schema_version: int
    objectives: tuple[str, ...]
    problems: tuple[str, ...]
    success_criteria: tuple[str, ...]
    constraints: tuple[str, ...]
    stakeholders: tuple[str, ...]
    decision_scope: str
    timeline: str = ""
    risk_tolerance: str = "medium"
    known_assumptions: tuple[str, ...] = ()  # references to evidence atom_ids

    def __post_init__(self) -> None:
        if not self.objectives:
            raise SchemaError("CaseDefinition needs at least one objective.")
        if not self.problems:
            raise SchemaError("CaseDefinition needs at least one problem statement.")
        if self.risk_tolerance not in RISK_TOLERANCE:
            raise SchemaError(f"risk_tolerance must be one of {RISK_TOLERANCE}.")


# --- Issue tree -----------------------------------------------------------------


@dataclass(frozen=True)
class IssueNode:
    """One node in the MECE issue tree. ``scope_tag`` is the deterministic
    handle used to check Mutual Exclusivity (no two nodes may claim the same
    tag) — a structural proxy for "this branch doesn't overlap that one",
    since true semantic MECE-ness cannot be checked by code (ADR-010 §6b)."""

    node_id: str
    title: str
    owner: str
    scope_tag: str
    parent_id: str | None = None
    hypothesis_refs: tuple[str, ...] = ()
    status: str = "open"  # open | answered | assumed

    def __post_init__(self) -> None:
        _require_slug(self.node_id, "node_id")
        if not self.owner:
            raise SchemaError(f"{self.node_id}: every issue node needs an owner.")
        if not self.scope_tag:
            raise SchemaError(f"{self.node_id}: every issue node needs a scope_tag.")


@dataclass(frozen=True)
class IssueTree:
    nodes: tuple[IssueNode, ...]

    def __post_init__(self) -> None:
        if not self.nodes:
            raise SchemaError("IssueTree needs at least one node.")
        ids = [n.node_id for n in self.nodes]
        if len(ids) != len(set(ids)):
            dupes = sorted({i for i in ids if ids.count(i) > 1})
            raise SchemaError(f"duplicate node_id(s): {dupes}.")

    def leaves(self) -> tuple[IssueNode, ...]:
        parents = {n.parent_id for n in self.nodes if n.parent_id}
        return tuple(n for n in self.nodes if n.node_id not in parents)


# --- Hypotheses -------------------------------------------------------------------


@dataclass(frozen=True)
class Hypothesis:
    """A testable claim about a root cause. Status and evidence links are
    deterministic outputs of ``consulting_validators.evaluate_hypothesis`` —
    an LLM proposes the ``statement``; whether it is supported, contradicted,
    or retired is computed from Evidence Store (P2) references, never
    self-declared."""

    hypothesis_id: str
    statement: str
    status: str = "untested"
    supporting_evidence: tuple[str, ...] = ()  # evidence atom_ids (P2)
    contradicting_evidence: tuple[str, ...] = ()
    confidence: float = 0.5
    dependencies: tuple[str, ...] = ()  # other hypothesis_ids

    def __post_init__(self) -> None:
        _require_slug(self.hypothesis_id, "hypothesis_id")
        if not self.statement:
            raise SchemaError(f"{self.hypothesis_id}: needs a statement.")
        if self.status not in HYPOTHESIS_STATUSES:
            raise SchemaError(f"status must be one of {HYPOTHESIS_STATUSES}.")
        if not 0.0 <= self.confidence <= 1.0:
            raise SchemaError(
                f"{self.hypothesis_id}: confidence must be in [0, 1], got "
                f"{self.confidence}."
            )


# --- Research planning -----------------------------------------------------------


@dataclass(frozen=True)
class ResearchTask:
    task_id: str
    issue_node_ref: str
    assigned_analyst: str
    objective: str
    evidence_requirements: tuple[str, ...] = ()
    expected_deliverable: str = ""

    def __post_init__(self) -> None:
        _require_slug(self.task_id, "task_id")
        if not self.assigned_analyst:
            raise SchemaError(f"{self.task_id}: needs an assigned_analyst.")
        if not self.objective:
            raise SchemaError(f"{self.task_id}: needs an objective.")


@dataclass(frozen=True)
class ResearchPlan:
    tasks: tuple[ResearchTask, ...]

    def coverage(self, tree: IssueTree) -> tuple[str, ...]:
        """Leaf node_ids in ``tree`` with NO assigned research task — the
        deterministic gap list ``consulting_validators`` rejects on."""
        assigned = {t.issue_node_ref for t in self.tasks}
        return tuple(n.node_id for n in tree.leaves() if n.node_id not in assigned)


# --- Strategic options & recommendations ------------------------------------------

# Criteria the ranker scores on (ADR-010 §6b). Each is declared by the LLM in
# [0, 1] on a "higher is better" scale — inverted criteria (complexity, risk,
# dependency burden, time-to-value) are declared as their INVERSE (e.g.
# "low complexity" = 0.9), so every score in this dict means the same
# direction and the ranker's weighted sum never has to guess a sign.
CRITERIA = (
    "strategic_value",
    "business_impact",
    "low_complexity",
    "low_execution_risk",
    "confidence",
    "evidence_quality",
    "low_dependency_burden",
    "fast_time_to_value",
)


@dataclass(frozen=True)
class StrategicOption:
    option_id: str
    title: str
    description: str
    benefits: tuple[str, ...]
    risks: tuple[str, ...]
    trade_offs: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    scores: dict[str, float]  # one entry per CRITERIA name, each in [0, 1]
    dependencies: tuple[str, ...] = ()  # DependencyEdge ids or capability names
    estimated_effort_months: float = 0.0

    def __post_init__(self) -> None:
        _require_slug(self.option_id, "option_id")
        if not self.title:
            raise SchemaError(f"{self.option_id}: needs a title.")
        missing = [c for c in CRITERIA if c not in self.scores]
        if missing:
            raise SchemaError(f"{self.option_id}: missing score(s) {missing}.")
        out_of_range = [c for c in CRITERIA if not 0.0 <= self.scores[c] <= 1.0]
        if out_of_range:
            raise SchemaError(
                f"{self.option_id}: score(s) {out_of_range} must be in [0, 1]."
            )


@dataclass(frozen=True)
class Recommendation:
    """Output of ``recommendation_ranker.rank`` — ``rank`` and
    ``composite_score`` are ALWAYS computed by code, never the LLM's own
    claimed ordering (the same discipline P1 applies to a derived ledger
    value)."""

    option_id: str
    rank: int
    composite_score: float
    status: str = "recommended"  # recommended | rejected
    rejection_reason: str = ""


# --- Dependency graph --------------------------------------------------------------


@dataclass(frozen=True)
class DependencyEdge:
    from_id: str
    to_id: str
    dependency_type: str
    description: str = ""

    def __post_init__(self) -> None:
        if self.dependency_type not in DEPENDENCY_TYPES:
            raise SchemaError(f"dependency_type must be one of {DEPENDENCY_TYPES}.")
        if self.from_id == self.to_id:
            raise SchemaError(f"{self.from_id}: cannot depend on itself.")


# --- Scenarios & sensitivity --------------------------------------------------------


@dataclass(frozen=True)
class ScenarioAssumption:
    """A named scenario as a set of assumption-value overrides. Deciding
    WHICH scenarios matter (bull/base/bear, or something case-specific) is
    still an LLM judgment; evaluating each one's numeric consequence is
    mechanical (``scenario_evaluator.py``, reusing P1's ledger arithmetic)."""

    scenario_id: str
    label: str
    overrides: dict[str, Decimal]  # ledger entry id -> override value
    probability: float | None = None
    narrative: str = ""

    def __post_init__(self) -> None:
        if not self.overrides:
            raise SchemaError(f"{self.scenario_id}: needs at least one override.")
        if self.probability is not None and not 0.0 <= self.probability <= 1.0:
            raise SchemaError(f"{self.scenario_id}: probability must be in [0, 1].")


@dataclass(frozen=True)
class CapabilityFlag:
    capability: str
    available: bool
    category: str
    rationale: str = ""

    def __post_init__(self) -> None:
        if self.category not in CAPABILITY_CATEGORIES:
            raise SchemaError(f"category must be one of {CAPABILITY_CATEGORIES}.")


@dataclass(frozen=True)
class SensitivityResult:
    """One assumption's impact: recomputing every dependent formula at its
    stated low/high bound. ``swing`` is the largest absolute change any
    dependent derived value underwent — the deterministic answer to "how much
    does this assumption matter", computed, never asserted."""

    assumption_id: str
    low_value: Decimal
    high_value: Decimal
    affected: tuple[str, ...]  # derived entry ids whose value changed
    swing: Decimal = field(default=Decimal(0))
