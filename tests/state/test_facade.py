"""M1.3 tests for the Engagement facade and the curated public surface."""

from __future__ import annotations

import state
from state import Engagement, EngagementProtocol, LifecycleStatus


def _engagement() -> Engagement:
    return Engagement.create(engagement_id="eng_1", tenant_id="t_1", slug="demo")


def test_create_yields_valid_bare_state() -> None:
    s = _engagement().get_state()
    assert s.status is LifecycleStatus.INTAKE
    assert s.problem is None
    assert s.evidence == []
    assert s.metadata.engagement_id == "eng_1"


def test_from_state_wraps_same_state() -> None:
    s = _engagement().get_state()
    assert Engagement.from_state(s).get_state() is s


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
    }


EXPECTED_PUBLIC_API = {
    # facade
    "Engagement",
    "EngagementProtocol",
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
