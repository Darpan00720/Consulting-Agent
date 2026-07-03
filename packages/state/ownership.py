"""Ownership matrices — data only, no enforcement (M1.7.6, design DD-1..DD-4).

Three frozen datasets make the repository's ownership truth machine-readable:

- ``COMPONENT_OWNERSHIP`` — which code component owns which writable runtime
  resource (exactly one writer per resource; write sets pairwise disjoint).
- ``SECTION_OWNERSHIP`` — the ADR-002 §Agent Read/Write Matrix, transcribed
  verbatim and mapped onto ``EngagementState`` fields (drift-tested).
- ``EVENT_OWNERSHIP`` — every ``EventType`` mapped to its writing role(s) and
  affected section(s), from the ADR-002 event catalog's By/Effect columns.

Nothing here decides or blocks anything: **enforcement is deliberately
absent** until M6's Agent Manager (the recorded TD-003 plan). Read access is
ADR-002's default — all agents read the whole state (tenant-scoping only) —
so only deviations are noted. ``Role`` seeds M6's role registry
(additive-frozen namespace, ADR-005 names). Internal module: not part of the
public API.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from state.events import EventType


class Role(StrEnum):
    """ADR-005 agent roles + externals + ADR-002 collective markers.

    ``ALL``, ``ANALYSTS``, and ``OWNER`` are collective markers used by the
    ADR-002 matrix, not concrete roles.
    """

    MANAGER = "manager"
    CLASSIFIER = "classifier"
    GAP_AGENT = "gap_agent"
    PLANNER = "planner"
    FRAMEWORK_SELECTOR = "framework_selector"
    ISSUE_TREE_GENERATOR = "issue_tree_generator"
    KNOWLEDGE_AGENT = "knowledge_agent"
    FINANCIAL_ANALYST = "financial_analyst"
    MARKET_ANALYST = "market_analyst"
    OPERATIONS_ANALYST = "operations_analyst"
    STRATEGY_ANALYST = "strategy_analyst"
    RISK_ANALYST = "risk_analyst"
    REVIEWER = "reviewer"
    CHALLENGER = "challenger"
    REPORT_WRITER = "report_writer"
    KNOWLEDGE_CURATOR = "knowledge_curator"
    HUMAN = "human"
    SYSTEM = "system"
    # collective markers (ADR-002 matrix vocabulary)
    ALL = "all"
    ANALYSTS = "analysts"
    OWNER = "owner"


@dataclass(frozen=True)
class ComponentOwnership:
    """One row of the component-level ownership matrix (design §Ownership)."""

    component: str
    owner: str
    reads: tuple[str, ...]
    writes: tuple[str, ...]  # runtime resources this component ALONE may write
    reason: str
    evidence: str
    enforcement: str
    status: str  # "verified" | "design"


@dataclass(frozen=True)
class SectionOwnership:
    """One ADR-002 matrix row, mapped onto EngagementState fields.

    ``fields`` are the aggregate's field names this section covers (empty for
    the Audit Trail, which lives in the committed log, not the state).
    ``adr`` is False only for implementation-era fields absent from ADR-002.
    """

    section: str
    fields: tuple[str, ...]
    write: tuple[Role, ...]
    update: tuple[Role, ...]
    approve: tuple[Role, ...] = ()
    reject: tuple[Role, ...] = ()
    adr: bool = True
    note: str = ""


@dataclass(frozen=True)
class EventOwnership:
    """Writing role(s) and affected section(s) for one event type."""

    writers: tuple[Role, ...]
    sections: tuple[str, ...]


COMPONENT_OWNERSHIP: tuple[ComponentOwnership, ...] = (
    ComponentOwnership(
        "Facade (Engagement)",
        "S5 wiring layer",
        reads=("committed snapshot",),
        writes=(),
        reason="wiring owns provenance, never data; delegates only",
        evidence="F1-F3, F7; facade module contract",
        enforcement="tests today (S6 freeze, F-suite)",
        status="verified",
    ),
    ComponentOwnership(
        "AppendPipeline",
        "S4 orchestration",
        reads=("committed snapshot",),
        writes=("candidate commit",),
        reason="fixed phase order; no arithmetic (P17), no rules (P19)",
        evidence="P1-P20; pipeline module contract",
        enforcement="tests today (P-suite)",
        status="verified",
    ),
    ComponentOwnership(
        "StateUpdater",
        "S4 commit point",
        reads=("committed snapshot",),
        writes=("committed snapshot",),
        reason="the single mutation point: make_committed + one reference swap",
        evidence="P9, P21-P23; commit module contract",
        enforcement="tests today; M1.8 preserves the atomic-commit invariant",
        status="verified",
    ),
    ComponentOwnership(
        "Projection (apply/project)",
        "M1.5 / M1.7.2",
        reads=("events", "state (pure input)"),
        writes=(),
        reason="pure fold; sole deriving authority for state_version",
        evidence="M1.5 purity/determinism tests; M1.7.2 stamp tests",
        enforcement="tests today (projection suite)",
        status="verified",
    ),
    ComponentOwnership(
        "Validation Runner",
        "M1.6",
        reads=("state",),
        writes=("validation report",),
        reason="the only orchestrator of rules; mints ValidationReport",
        evidence="M1.6 runner tests; P19 (pipeline uses runner only)",
        enforcement="tests today",
        status="verified",
    ),
    ComponentOwnership(
        "Validation Registry (5 groups)",
        "M1.6 / M1.7.5",
        reads=("state",),
        writes=(),
        reason="pure findings; rules decide, never act",
        evidence="registry architecture + per-rule tests",
        enforcement="tests today",
        status="verified",
    ),
    ComponentOwnership(
        "Replay Integrity",
        "M1.7.4",
        reads=("log", "snapshot"),
        writes=(),
        reason="verifies, never repairs (no renumbering, no synthesis)",
        evidence="R1-R18 tests; integrity module contract",
        enforcement="tests today; M1.8/M1.9 call sites",
        status="verified",
    ),
    ComponentOwnership(
        "Sequence Allocator",
        "S2 arithmetic",
        reads=("unassigned events",),
        writes=("stamped event copies",),
        reason="arithmetic only; sole assigner of seq (once, at allocation)",
        evidence="A1-A8; sequencing module contract",
        enforcement="tests today",
        status="verified",
    ),
    ComponentOwnership(
        "Version Manager (versioning)",
        "S2 arithmetic",
        reads=("event metadata",),
        writes=(),
        reason="pure derivation from event metadata only",
        evidence="V1-V7; P17/P18",
        enforcement="tests today",
        status="verified",
    ),
    ComponentOwnership(
        "Concurrency Guard",
        "S3 decisions",
        reads=("committed facts", "candidate events"),
        writes=(),
        reason="returns decisions; never mutates, allocates, or validates",
        evidence="G1-G16; guard module contract",
        enforcement="tests today",
        status="verified",
    ),
    ComponentOwnership(
        "Traceability Generator",
        "tooling (make traceability)",
        reads=("rule registry", "test tree", "ownership datasets"),
        writes=("traceability artifacts",),
        reason="generated-artifact discipline: sole writer of the matrix docs",
        evidence="generator + freshness/completeness tests",
        enforcement="tests today",
        status="verified",
    ),
    ComponentOwnership(
        "State Models",
        "M1.2",
        reads=(),
        writes=(),
        reason="no at-rest mutation path: snapshots are detached (D1); the "
        "only evolution is the append pipeline",
        evidence="M1.7.1 snapshot suite; F6",
        enforcement="tests today",
        status="verified",
    ),
    ComponentOwnership(
        "Events",
        "M1.4",
        reads=(),
        writes=(),
        reason="frozen models; the log is append-only by all, mutable by none",
        evidence="frozen configs; ADR-002 audit-trail row; R-tests",
        enforcement="by construction + tests",
        status="verified",
    ),
    ComponentOwnership(
        "Event Metadata (seq)",
        "S2-stamped envelope field",
        reads=(),
        writes=(),
        reason="written exactly once, at allocation, by the Sequence "
        "Allocator; never re-stamped (A7/A8, R5)",
        evidence="S2 + integrity tests",
        enforcement="tests today",
        status="verified",
    ),
    ComponentOwnership(
        "Knowledge Layer (vault/Graphify)",
        "ADR-003 (M2/M3)",
        reads=("vault content", "vault graph"),
        writes=("knowledge vault", "vault graph"),
        reason="humans + Curator (M9) author the vault; only 'make "
        "vault-index' rebuilds the graph; zero interaction with state",
        evidence="0 cross-imports; ADR-003; Graphify installation review",
        enforcement="M2 governance lint; M9 Curator",
        status="verified",
    ),
    ComponentOwnership(
        "Agent Manager (M6, future)",
        "ADR-005 executive",
        reads=("whole state",),
        writes=(),
        reason="will own lifecycle writes and serialize transitions per "
        "ADR-002; enforcement owner for every role-based rule (TD-003)",
        evidence="ADR-002 matrix; ADR-005 §3 Executive; TD-003 deferral",
        enforcement="M6 (itself)",
        status="design",
    ),
)


SECTION_OWNERSHIP: tuple[SectionOwnership, ...] = (
    SectionOwnership(
        "Engagement Metadata", ("metadata",), (Role.MANAGER,), (Role.MANAGER,)
    ),
    SectionOwnership(
        "Lifecycle Status",
        ("status", "phase_history", "quality_gates", "pending_requirements"),
        (Role.MANAGER,),
        (Role.MANAGER,),
        note="ADR-002 §2 audit fields included (M1.5 implementation correction)",
    ),
    SectionOwnership(
        "Problem Definition",
        ("problem",),
        (Role.CLASSIFIER,),
        (Role.CLASSIFIER, Role.HUMAN),
        (Role.HUMAN,),
        (Role.HUMAN,),
    ),
    SectionOwnership(
        "Objectives",
        ("objectives", "success_criteria"),
        (Role.CLASSIFIER,),
        (Role.CLASSIFIER, Role.HUMAN),
        (Role.HUMAN,),
        (Role.HUMAN,),
        note="success criteria are part of ADR-002 §4 Objectives",
    ),
    SectionOwnership(
        "Constraints",
        ("constraints",),
        (Role.CLASSIFIER,),
        (Role.CLASSIFIER, Role.HUMAN),
        (Role.HUMAN,),
        (Role.HUMAN,),
    ),
    SectionOwnership(
        "Stakeholders", ("stakeholders",), (Role.CLASSIFIER,), (Role.CLASSIFIER,)
    ),
    SectionOwnership(
        "Case Classification",
        ("classification",),
        (Role.CLASSIFIER,),
        (Role.CLASSIFIER, Role.MANAGER),
        (Role.MANAGER, Role.HUMAN),
        (Role.HUMAN,),
    ),
    SectionOwnership(
        "Information Gaps",
        ("information_gaps",),
        (Role.GAP_AGENT,),
        (Role.GAP_AGENT, Role.ANALYSTS, Role.HUMAN),
        (Role.HUMAN,),
        (Role.HUMAN,),
    ),
    SectionOwnership(
        "Assumption Ledger",
        ("assumptions",),
        (Role.ANALYSTS, Role.GAP_AGENT),
        (Role.OWNER,),
        (Role.REVIEWER,),
        (Role.REVIEWER, Role.CHALLENGER),
    ),
    SectionOwnership(
        "Engagement Plan",
        ("plan",),
        (Role.PLANNER,),
        (Role.PLANNER, Role.MANAGER),
    ),
    SectionOwnership(
        "Framework Selection",
        ("frameworks",),
        (Role.FRAMEWORK_SELECTOR,),
        (Role.FRAMEWORK_SELECTOR,),
        (Role.REVIEWER,),
        (Role.REVIEWER, Role.CHALLENGER),
    ),
    SectionOwnership(
        "Issue Tree",
        ("issue_tree",),
        (Role.ISSUE_TREE_GENERATOR,),
        (Role.ISSUE_TREE_GENERATOR, Role.ANALYSTS),
        (Role.REVIEWER,),
        (Role.REVIEWER,),
    ),
    SectionOwnership(
        "Knowledge References",
        ("knowledge_references",),
        (Role.KNOWLEDGE_AGENT,),
        (Role.KNOWLEDGE_AGENT,),
    ),
    SectionOwnership(
        "Evidence Ledger",
        ("evidence",),
        (Role.ANALYSTS, Role.KNOWLEDGE_AGENT),
        (Role.OWNER,),
        (Role.REVIEWER,),
        (Role.REVIEWER,),
    ),
    SectionOwnership(
        "Financial Analysis",
        ("financial_analysis",),
        (Role.FINANCIAL_ANALYST,),
        (Role.FINANCIAL_ANALYST,),
        (Role.REVIEWER,),
        (Role.REVIEWER, Role.CHALLENGER),
    ),
    SectionOwnership(
        "Market Analysis",
        ("market_analysis",),
        (Role.MARKET_ANALYST,),
        (Role.MARKET_ANALYST,),
        (Role.REVIEWER,),
        (Role.REVIEWER, Role.CHALLENGER),
    ),
    SectionOwnership(
        "Operations Analysis",
        ("operations_analysis",),
        (Role.OPERATIONS_ANALYST,),
        (Role.OPERATIONS_ANALYST,),
        (Role.REVIEWER,),
        (Role.REVIEWER, Role.CHALLENGER),
    ),
    SectionOwnership(
        "Strategy Analysis",
        ("strategy_analysis",),
        (Role.STRATEGY_ANALYST,),
        (Role.STRATEGY_ANALYST,),
        (Role.REVIEWER,),
        (Role.REVIEWER, Role.CHALLENGER),
    ),
    SectionOwnership(
        "Risk Analysis",
        ("risk_analysis",),
        (Role.RISK_ANALYST,),
        (Role.RISK_ANALYST,),
        (Role.REVIEWER,),
        (Role.REVIEWER, Role.CHALLENGER),
    ),
    SectionOwnership(
        "Reviewer Notes",
        ("reviewer_notes",),
        (Role.REVIEWER,),
        (Role.REVIEWER,),
        (Role.REVIEWER,),
        (Role.REVIEWER,),
    ),
    SectionOwnership(
        "Challenge Notes",
        ("challenge_notes",),
        (Role.CHALLENGER,),
        (Role.CHALLENGER,),
        (Role.CHALLENGER,),
        (Role.CHALLENGER,),
    ),
    SectionOwnership(
        "Recommendations",
        ("recommendations",),
        (Role.REPORT_WRITER,),
        (Role.REPORT_WRITER,),
        (Role.HUMAN, Role.MANAGER),
        (Role.CHALLENGER, Role.REVIEWER, Role.HUMAN),
    ),
    SectionOwnership(
        "Confidence Scores",
        ("confidence",),
        (Role.OWNER,),
        (Role.REPORT_WRITER, Role.MANAGER),
        note="ADR-002: created by section owners; rolled up by Report Writer",
    ),
    SectionOwnership(
        "Deliverables",
        ("deliverables",),
        (Role.REPORT_WRITER,),
        (Role.REPORT_WRITER,),
        (Role.HUMAN,),
    ),
    SectionOwnership(
        "Knowledge Links",
        ("knowledge_links",),
        (Role.KNOWLEDGE_CURATOR,),
        (Role.KNOWLEDGE_CURATOR,),
        note="read is tenant-scoped (ADR-002)",
    ),
    SectionOwnership(
        "Audit Trail",
        (),
        (Role.ALL,),
        (),
        note="append-only by all, mutable by none; lives in the committed "
        "log (Committed.log), not on EngagementState",
    ),
    SectionOwnership(
        "Projection Provenance",
        ("projection_version",),
        (Role.SYSTEM,),
        (),
        adr=False,
        note="implementation field (M1.5/M1.7.2): stamped only by project(); "
        "never agent-writable",
    ),
)


def _analysis_sections() -> tuple[str, ...]:
    return (
        "Financial Analysis",
        "Market Analysis",
        "Operations Analysis",
        "Strategy Analysis",
        "Risk Analysis",
    )


EVENT_OWNERSHIP: Mapping[EventType, EventOwnership] = MappingProxyType(
    {
        EventType.ENGAGEMENT_CREATED: EventOwnership(
            (Role.MANAGER,), ("Engagement Metadata", "Lifecycle Status")
        ),
        EventType.PROBLEM_DEFINED: EventOwnership(
            (Role.CLASSIFIER,), ("Problem Definition",)
        ),
        EventType.PROBLEM_UPDATED: EventOwnership(
            (Role.CLASSIFIER, Role.HUMAN), ("Problem Definition",)
        ),
        EventType.OBJECTIVES_RECORDED: EventOwnership(
            (Role.CLASSIFIER,), ("Objectives",)
        ),
        EventType.CONSTRAINTS_RECORDED: EventOwnership(
            (Role.CLASSIFIER,), ("Constraints",)
        ),
        EventType.STAKEHOLDERS_RECORDED: EventOwnership(
            (Role.CLASSIFIER,), ("Stakeholders",)
        ),
        EventType.CASE_CLASSIFIED: EventOwnership(
            (Role.CLASSIFIER,), ("Case Classification",)
        ),
        EventType.CASE_RECLASSIFIED: EventOwnership(
            (Role.CLASSIFIER, Role.MANAGER), ("Case Classification",)
        ),
        EventType.INFORMATION_GAP_IDENTIFIED: EventOwnership(
            (Role.GAP_AGENT,), ("Information Gaps",)
        ),
        EventType.GAP_ANSWERED: EventOwnership(
            (Role.HUMAN, Role.KNOWLEDGE_AGENT), ("Information Gaps",)
        ),
        EventType.GAP_ASSUMED: EventOwnership(
            (Role.GAP_AGENT, Role.ANALYSTS),
            ("Information Gaps", "Assumption Ledger"),
        ),
        EventType.ASSUMPTION_ADDED: EventOwnership(
            (Role.ANALYSTS,), ("Assumption Ledger",)
        ),
        EventType.ASSUMPTION_UPDATED: EventOwnership(
            (Role.OWNER,), ("Assumption Ledger",)
        ),
        EventType.ASSUMPTION_INVALIDATED: EventOwnership(
            (Role.REVIEWER, Role.CHALLENGER), ("Assumption Ledger",)
        ),
        EventType.ENGAGEMENT_PLAN_CREATED: EventOwnership(
            (Role.PLANNER,), ("Engagement Plan",)
        ),
        EventType.ENGAGEMENT_REPLANNED: EventOwnership(
            (Role.PLANNER,), ("Engagement Plan",)
        ),
        EventType.FRAMEWORK_SELECTED: EventOwnership(
            (Role.FRAMEWORK_SELECTOR,), ("Framework Selection",)
        ),
        EventType.FRAMEWORK_DESELECTED: EventOwnership(
            (Role.FRAMEWORK_SELECTOR, Role.REVIEWER), ("Framework Selection",)
        ),
        EventType.ISSUE_TREE_GENERATED: EventOwnership(
            (Role.ISSUE_TREE_GENERATOR,), ("Issue Tree",)
        ),
        EventType.ISSUE_TREE_NODE_UPDATED: EventOwnership(
            (Role.ISSUE_TREE_GENERATOR, Role.ANALYSTS), ("Issue Tree",)
        ),
        EventType.KNOWLEDGE_RETRIEVED: EventOwnership(
            (Role.KNOWLEDGE_AGENT,), ("Knowledge References",)
        ),
        EventType.EVIDENCE_ADDED: EventOwnership(
            (Role.ANALYSTS, Role.KNOWLEDGE_AGENT), ("Evidence Ledger",)
        ),
        EventType.EVIDENCE_VALIDATED: EventOwnership(
            (Role.REVIEWER,), ("Evidence Ledger",)
        ),
        EventType.EVIDENCE_REJECTED: EventOwnership(
            (Role.REVIEWER,), ("Evidence Ledger",)
        ),
        EventType.EVIDENCE_MARKED_STALE: EventOwnership(
            (Role.REVIEWER, Role.SYSTEM), ("Evidence Ledger",)
        ),
        EventType.SPECIALIST_ANALYSIS_STARTED: EventOwnership(
            (Role.ANALYSTS,), _analysis_sections()
        ),
        EventType.FINDING_RECORDED: EventOwnership(
            (Role.ANALYSTS,), _analysis_sections()
        ),
        EventType.SPECIALIST_ANALYSIS_COMPLETED: EventOwnership(
            (Role.ANALYSTS,), _analysis_sections()
        ),
        EventType.REVIEWER_REVIEWED: EventOwnership(
            (Role.REVIEWER,), ("Reviewer Notes",)
        ),
        EventType.REVIEWER_APPROVED: EventOwnership(
            (Role.REVIEWER,), ("Reviewer Notes", "Lifecycle Status")
        ),
        EventType.REVIEWER_REJECTED: EventOwnership(
            (Role.REVIEWER,), ("Reviewer Notes", "Lifecycle Status")
        ),
        EventType.CHALLENGE_RECORDED: EventOwnership(
            (Role.CHALLENGER,), ("Challenge Notes",)
        ),
        EventType.CHALLENGER_CLEARED: EventOwnership(
            (Role.CHALLENGER,), ("Challenge Notes", "Lifecycle Status")
        ),
        EventType.CHALLENGER_REJECTED: EventOwnership(
            (Role.CHALLENGER,), ("Challenge Notes", "Lifecycle Status")
        ),
        EventType.RECOMMENDATION_DRAFTED: EventOwnership(
            (Role.REPORT_WRITER,), ("Recommendations",)
        ),
        EventType.CONFIDENCE_SCORED: EventOwnership(
            (Role.REPORT_WRITER, Role.MANAGER), ("Confidence Scores",)
        ),
        EventType.RECOMMENDATION_ACCEPTED: EventOwnership(
            (Role.HUMAN, Role.MANAGER), ("Recommendations",)
        ),
        EventType.REPORT_GENERATED: EventOwnership(
            (Role.REPORT_WRITER,), ("Deliverables",)
        ),
        EventType.DECK_GENERATED: EventOwnership(
            (Role.REPORT_WRITER,), ("Deliverables",)
        ),
        EventType.MODEL_GENERATED: EventOwnership(
            (Role.REPORT_WRITER,), ("Deliverables",)
        ),
        EventType.HUMAN_INPUT_REQUESTED: EventOwnership(
            (Role.MANAGER,), ("Lifecycle Status",)
        ),
        EventType.HUMAN_INPUT_PROVIDED: EventOwnership(
            (Role.HUMAN,), ("Lifecycle Status",)
        ),
        EventType.PHASE_TRANSITIONED: EventOwnership(
            (Role.MANAGER,), ("Lifecycle Status",)
        ),
        EventType.ENGAGEMENT_COMPLETED: EventOwnership(
            (Role.MANAGER,), ("Lifecycle Status",)
        ),
        EventType.ENGAGEMENT_FAILED: EventOwnership(
            (Role.SYSTEM,), ("Lifecycle Status",)
        ),
        EventType.ENGAGEMENT_ABORTED: EventOwnership(
            (Role.HUMAN,), ("Lifecycle Status",)
        ),
        EventType.LESSON_CAPTURED: EventOwnership(
            (Role.KNOWLEDGE_CURATOR,), ("Knowledge Links",)
        ),
        EventType.KNOWLEDGE_GRAPH_LINKED: EventOwnership(
            (Role.KNOWLEDGE_CURATOR,), ("Knowledge Links",)
        ),
        EventType.PROFILE_UPDATED: EventOwnership(
            (Role.KNOWLEDGE_CURATOR,), ("Knowledge Links",)
        ),
    }
)
