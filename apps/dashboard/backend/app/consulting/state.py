"""Engagement state — the mutable object the Consulting Workflow Engine builds
up over one engagement's lifecycle.

Mutable by design, same distinction the platform already draws elsewhere
(frozen dataclasses for values, plain dataclasses for the stateful containers
that accumulate them — ``AgentRegistry``, ``MemoryRegistry``,
``ToolRegistry``). ``EngagementState`` is this package's equivalent: a
container that ``tracking.py``/``engine.py`` mutate in place as an engagement
progresses.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum

from app.consulting.models import (
    Artifact,
    Assumption,
    ConsultingStage,
    Decision,
    EngagementCategory,
    Evidence,
    Hypothesis,
    QualityGateResult,
    Recommendation,
)

# ---- Stage 1: Problem Definition -------------------------------------------


@dataclass(frozen=True)
class ProblemDefinition:
    objective: str = ""
    scope: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    stakeholders: tuple[str, ...] = ()
    success_metrics: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()


# ---- Stage 3: Issue Tree (MECE) --------------------------------------------


@dataclass(frozen=True)
class IssueNode:
    id: str
    question: str
    parent_id: str | None
    hypothesis_ids: tuple[str, ...] = ()
    owner: str = ""


@dataclass
class IssueTree:
    root_id: str
    nodes: dict[str, IssueNode] = field(default_factory=dict)
    mece_validated: bool = False


def validate_mece(tree: IssueTree) -> tuple[bool, tuple[str, ...]]:
    """Best-effort STRUCTURAL MECE validation — honest scope limit: this
    checks the shape a MECE tree must have (single root, every parent
    reference resolves, no cycles, no duplicate sibling questions feeding the
    same parent), not that the decomposition is semantically exhaustive —
    proving actual exhaustiveness requires domain judgment no static check
    can make. The same "structural, not a formal proof" caveat the platform
    already applies to W6's dependency-graph validation.
    """
    issues: list[str] = []
    nodes = tree.nodes

    if tree.root_id not in nodes:
        return False, ("root_id not present in nodes",)
    roots = [n for n in nodes.values() if n.parent_id is None]
    if len(roots) != 1:
        issues.append(f"expected exactly one root node, found {len(roots)}")
    elif roots[0].id != tree.root_id:
        issues.append("declared root_id does not match the actual root node")

    for node in nodes.values():
        if node.parent_id is not None and node.parent_id not in nodes:
            issues.append(
                f"node {node.id!r} references missing parent {node.parent_id!r}"
            )

    # Cycle detection: walk each node toward the root; must terminate.
    for node in nodes.values():
        seen: set[str] = set()
        current: str | None = node.id
        steps = 0
        while current is not None:
            if current in seen:
                issues.append(f"cycle detected reaching node {node.id!r}")
                break
            seen.add(current)
            parent = nodes.get(current)
            current = parent.parent_id if parent else None
            steps += 1
            if steps > len(nodes) + 1:
                issues.append(f"cycle detected reaching node {node.id!r}")
                break

    # Mutual-exclusivity proxy: no two siblings under the same parent share
    # an identical question (a real MECE break the tree can detect).
    by_parent: dict[str | None, list[str]] = {}
    for node in nodes.values():
        by_parent.setdefault(node.parent_id, []).append(node.question.strip().lower())
    for parent_id, questions in by_parent.items():
        if len(questions) != len(set(questions)):
            issues.append(f"duplicate sibling questions under parent {parent_id!r}")

    return (len(issues) == 0), tuple(issues)


# ---- Stage 4: Analysis Planning --------------------------------------------


@dataclass(frozen=True)
class AnalysisPlan:
    required_analyses: tuple[str, ...] = ()
    required_frameworks: tuple[str, ...] = ()
    required_data: tuple[str, ...] = ()
    required_tools: tuple[str, ...] = ()
    required_experts: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()


# ---- Stage 9: Implementation Roadmap ---------------------------------------


@dataclass(frozen=True)
class RoadmapPhase:
    name: str
    timeline: str
    owners: tuple[str, ...]
    dependencies: tuple[str, ...] = ()
    quick_win: bool = False
    kpis: tuple[str, ...] = ()


@dataclass(frozen=True)
class Roadmap:
    phases: tuple[RoadmapPhase, ...] = ()


@dataclass(frozen=True)
class RiskRegisterEntry:
    risk: str
    likelihood: str
    impact: str
    mitigation: str
    owner: str = ""


# ---- Engagement lifecycle ----------------------------------------------------


class EngagementStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class StageOutcome(StrEnum):
    PASSED = "passed"
    BLOCKED = "blocked"
    IN_PROGRESS = "in_progress"


@dataclass
class StageHistoryEntry:
    stage: ConsultingStage
    entered_at: float
    exited_at: float | None = None
    outcome: StageOutcome = StageOutcome.IN_PROGRESS
    gate_results: tuple[QualityGateResult, ...] = ()


@dataclass
class EngagementState:
    """The engine's working state for ONE engagement. Mutated in place by
    ``tracking.py`` and ``engine.py`` — never constructed with pre-filled
    hypotheses/evidence/etc.; every mutation goes through a tracking function
    so invariants (evidence-must-exist, etc.) are enforced at a single choke
    point rather than scattered across call sites."""

    engagement_id: str
    workflow_id: str
    workflow_version: str
    category: EngagementCategory
    trace_id: str = ""
    status: EngagementStatus = EngagementStatus.PENDING
    current_stage: ConsultingStage | None = None
    stage_history: list[StageHistoryEntry] = field(default_factory=list)

    problem: ProblemDefinition = field(default_factory=ProblemDefinition)
    hypotheses: dict[str, Hypothesis] = field(default_factory=dict)
    assumptions: dict[str, Assumption] = field(default_factory=dict)
    evidence: dict[str, Evidence] = field(default_factory=dict)
    issue_tree: IssueTree | None = None
    analysis_plan: AnalysisPlan = field(default_factory=AnalysisPlan)
    analysis_findings: list[str] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    recommendations: dict[str, Recommendation] = field(default_factory=dict)
    roadmap: Roadmap = field(default_factory=Roadmap)
    risk_register: list[RiskRegisterEntry] = field(default_factory=list)
    artifacts: dict[str, Artifact] = field(default_factory=dict)

    created_at: float = field(default_factory=time.time)
