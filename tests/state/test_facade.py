"""M1.3 tests for the Engagement facade and the curated public surface.

M1.7.1 (design D1) adds the snapshot-semantics contract: state crosses the
facade boundary only as detached deep copies, with no aliasing anywhere in the
object graph.
"""

from __future__ import annotations

from typing import Any

import state
from state import (
    AnalysisBlock,
    ConfidenceReport,
    Deliverable,
    DeliverableKind,
    Engagement,
    EngagementProtocol,
    EngagementState,
    Evidence,
    EvidenceType,
    Finding,
    Gap,
    GateResult,
    IssueNode,
    LifecycleStatus,
    NextStep,
    PendingRequirement,
    PhaseRecord,
    ProblemDefinition,
    QualityGate,
    Recommendations,
)


def _engagement() -> Engagement:
    return Engagement.create(engagement_id="eng_1", tenant_id="t_1", slug="demo")


def _rich_engagement() -> Engagement:
    """An engagement whose state populates models, lists, and the dict field."""
    ev = Evidence(claim="c", type=EvidenceType.CLIENT_FACT, confidence=0.5)
    base = _engagement().get_state()
    rich = base.model_copy(
        update={
            "problem": ProblemDefinition(raw_input="raw"),
            "success_criteria": ["criterion"],
            "evidence": [ev],
            "information_gaps": [Gap(question="q")],
            "issue_tree": [IssueNode(question="q", owner="o")],
            "financial_analysis": AnalysisBlock(
                findings=[Finding(question="q", evidence_refs=[ev.id])]
            ),
            "recommendations": Recommendations(
                decision="d", next_steps=[NextStep(step="s")], risks=["r"]
            ),
            "confidence": ConfidenceReport(overall=0.5, by_section={"fin": 0.6}),
            "deliverables": [Deliverable(kind=DeliverableKind.REPORT)],
            "phase_history": [PhaseRecord(phase=LifecycleStatus.INTAKE)],
            "quality_gates": [QualityGate(gate="reviewer", result=GateResult.PASS)],
            "pending_requirements": [PendingRequirement(description="d")],
        }
    )
    return Engagement.from_state(rich)


def _mutable_containers(obj: Any, acc: set[int]) -> None:
    """Collect ids of every mutable container reachable from a state."""
    if isinstance(obj, list):
        acc.add(id(obj))
        for item in obj:
            _mutable_containers(item, acc)
    elif isinstance(obj, dict):
        acc.add(id(obj))
        for item in obj.values():
            _mutable_containers(item, acc)
    elif hasattr(type(obj), "model_fields"):  # pydantic model
        acc.add(id(obj))
        for name in type(obj).model_fields:
            _mutable_containers(getattr(obj, name), acc)


def test_create_yields_valid_bare_state() -> None:
    s = _engagement().get_state()
    assert s.status is LifecycleStatus.INTAKE
    assert s.problem is None
    assert s.evidence == []
    assert s.metadata.engagement_id == "eng_1"


def test_from_state_copies_on_ingest() -> None:
    caller_state = _rich_engagement().get_state()
    e = Engagement.from_state(caller_state)
    assert e.get_state() is not caller_state
    caller_state.evidence.clear()
    caller_state.status = LifecycleStatus.ABORTED
    fresh = e.get_state()
    assert len(fresh.evidence) == 1
    assert fresh.status is LifecycleStatus.INTAKE


def test_get_state_returns_detached_snapshot() -> None:
    e = _rich_engagement()
    pristine = e.get_state()
    snapshot = e.get_state()
    snapshot.evidence.append(
        Evidence(claim="x", type=EvidenceType.CLIENT_FACT, confidence=0.1)
    )
    snapshot.metadata.slug = "mutated"
    assert e.get_state() == pristine


def test_get_state_snapshots_equal_but_distinct() -> None:
    e = _rich_engagement()
    a, b = e.get_state(), e.get_state()
    assert a == b
    assert a is not b
    assert a.metadata is not b.metadata
    assert a.evidence is not b.evidence
    assert a.evidence[0] is not b.evidence[0]


def test_snapshot_mutation_does_not_affect_serialization() -> None:
    e = _rich_engagement()
    before = e.to_json()
    snapshot = e.get_state()
    snapshot.issue_tree.clear()
    assert snapshot.confidence is not None
    snapshot.confidence.by_section["fin"] = 0.1
    assert e.to_json() == before


def test_top_level_identity_regression() -> None:
    e = _rich_engagement()
    pristine = e.get_state()
    snapshot = e.get_state()
    snapshot.status = LifecycleStatus.FAILED
    snapshot.problem = ProblemDefinition(raw_input="replaced")
    snapshot.evidence = []
    assert e.get_state() == pristine


def test_recursive_identity_regression() -> None:
    e = _rich_engagement()
    # Both snapshots must stay alive for the whole comparison: freeing one lets
    # the allocator reuse its addresses, making id()-sets collide spuriously.
    a, b = e.get_state(), e.get_state()
    first: set[int] = set()
    second: set[int] = set()
    _mutable_containers(a, first)
    _mutable_containers(b, second)
    assert first, "walker found no containers — fixture or walker broken"
    assert first.isdisjoint(second), "snapshots share mutable objects"


def test_mutable_collection_regression() -> None:
    e = _rich_engagement()
    pristine = e.get_state()
    snapshot = e.get_state()
    # every top-level list field on the aggregate (populated or empty)
    list_fields = [
        name
        for name in EngagementState.model_fields
        if isinstance(getattr(snapshot, name), list)
    ]
    assert len(list_fields) >= 10
    for name in list_fields:
        getattr(snapshot, name).append("sentinel")
    # nested lists inside nested models
    assert snapshot.financial_analysis is not None
    snapshot.financial_analysis.findings[0].evidence_refs.append("ghost")
    assert snapshot.recommendations is not None
    snapshot.recommendations.risks.clear()
    # the one dict field in the aggregate graph
    assert snapshot.confidence is not None
    snapshot.confidence.by_section["injected"] = 0.9
    assert e.get_state() == pristine


def test_json_round_trip() -> None:
    e = _engagement()
    restored = Engagement.from_json(e.to_json())
    assert restored.get_state() == e.get_state()


def test_validate_passes_on_valid_state() -> None:
    _engagement().validate()  # must not raise


def test_conforms_to_protocol() -> None:
    engagement: EngagementProtocol = _engagement()
    assert engagement.get_state().status is LifecycleStatus.INTAKE


def test_facade_public_api_is_frozen() -> None:
    public = {
        name
        for name in dir(Engagement)
        if not name.startswith("_") and callable(getattr(Engagement, name))
    }
    assert public == {
        "create",
        "from_state",
        "from_json",
        "get_state",
        "validate",
        "to_json",
        # M1.7.3-S5: the M1.3-reserved event API extension
        "append_event",
        "append_events",
        "current_version",
        "current_sequence",
    }


EXPECTED_PUBLIC_API = {
    # facade
    "Engagement",
    "EngagementProtocol",
    # append API (M1.7.3-S5)
    "AppendError",
    "AppendErrorCode",
    "AppendResult",
    "AppendUnsupportedError",
    "EventAdmissionError",
    "VersionConflictError",
    # validation surface (M1.7.3-S5)
    "StateValidationError",
    "ValidationGroup",
    "ValidationReport",
    "Violation",
    "ViolationSeverity",
    # root
    "EngagementState",
    "EngagementMetadata",
    "LifecycleStatus",
    # ledgers
    "Evidence",
    "Assumption",
    "EvidenceType",
    "AssumptionStatus",
    # scoping
    "Document",
    "ProblemDefinition",
    "Objective",
    "Constraint",
    "Stakeholder",
    "CaseClassification",
    "Gap",
    "CaseArchetype",
    "ObjectiveSource",
    "ConstraintType",
    "StakeholderRelationship",
    "GapCriticality",
    "GapStatus",
    # planning
    "PlanStep",
    "EngagementPlan",
    "FrameworkSelection",
    "IssueNode",
    "KnowledgeReference",
    "PlanStepStatus",
    "IssueNodeStatus",
    "KnowledgeRefKind",
    # analysis
    "Finding",
    "SensitivityCase",
    "AnalysisBlock",
    "AnalysisStatus",
    # governance
    "ReviewCheck",
    "ReviewerNotes",
    "ChallengeNotes",
    "ReviewCheckName",
    "CheckResult",
    "ReviewVerdict",
    "ChallengeVerdict",
    # output
    "NextStep",
    "RejectedAlternative",
    "Recommendations",
    "ConfidenceReport",
    "Deliverable",
    "KnowledgeLink",
    "RecommendationStatus",
    "DeliverableKind",
    "DeliverableStatus",
    # lifecycle audit
    "PhaseRecord",
    "QualityGate",
    "PendingRequirement",
    "GateResult",
    "PendingKind",
    # value objects
    "ConfidenceScore",
    "Identifier",
    "Reference",
    "DomainObject",
    "new_id",
    # strongly-typed identifiers
    "EventId",
    "EngagementId",
    "AssumptionId",
    "EvidenceId",
    "GapId",
    "IssueNodeId",
    "FrameworkId",
    "DeliverableId",
    "RecommendationId",
    # events
    "Event",
    "EventMetadata",
    "EventType",
    "EventCategory",
    "EventSource",
    "EVENT_CATEGORIES",
}


def test_public_surface_matches_allowlist() -> None:
    assert set(state.__all__) == EXPECTED_PUBLIC_API
    for name in EXPECTED_PUBLIC_API:
        assert hasattr(state, name), f"missing public export: {name}"


def test_internal_helpers_not_exported() -> None:
    assert "_validate_evidence_type" not in state.__all__
    assert not hasattr(state, "_validate_evidence_type")
