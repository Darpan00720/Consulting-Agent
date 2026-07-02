"""M1.5 coverage: a log exercising every reducer projects deterministically."""

from __future__ import annotations

from typing import Any

from state import events as ev
from state.enums import LifecycleStatus
from state.events import Event, EventMetadata, EventSource
from state.ledgers import Assumption, Evidence, EvidenceType
from state.projection import project
from state.sections.analysis import Finding
from state.sections.enums import (
    AnalysisStatus,
    CaseArchetype,
    DeliverableKind,
    KnowledgeRefKind,
)
from state.sections.governance import ChallengeNotes, ReviewerNotes
from state.sections.output import ConfidenceReport, Deliverable, Recommendations
from state.sections.planning import (
    EngagementPlan,
    FrameworkSelection,
    IssueNode,
    KnowledgeReference,
)
from state.sections.scoping import (
    CaseClassification,
    Constraint,
    Gap,
    Objective,
    Stakeholder,
)


def _m(**kwargs: Any) -> EventMetadata:
    return EventMetadata(
        engagement_id="eng", actor="system", source=EventSource.SYSTEM, **kwargs
    )


def _full_log() -> list[Event]:
    gap = Gap(question="what is churn?")
    assumption = Assumption(
        statement="churn 5%", value="5%", rationale="base", owner="fin", confidence=0.5
    )
    framework = FrameworkSelection(name="Profit tree")
    node = IssueNode(question="price or volume?")
    evidence = Evidence(
        claim="rev $600M", type=EvidenceType.CLIENT_FACT, confidence=0.9
    )
    cls = CaseClassification(
        primary_archetype=CaseArchetype.PROFITABILITY, confidence=0.8
    )
    deliverable = Deliverable(kind=DeliverableKind.REPORT)
    return [
        ev.EngagementCreated(metadata=_m(), slug="demo", tenant_id="t"),
        ev.ProblemDefined(metadata=_m(), raw_input="margin down", real_question="why?"),
        ev.ProblemUpdated(metadata=_m(), real_question="why did margin fall?"),
        ev.ObjectivesRecorded(
            metadata=_m(),
            objectives=[Objective(statement="restore margin")],
            success_criteria=["margin >= 4%"],
        ),
        ev.ConstraintsRecorded(
            metadata=_m(), constraints=[Constraint(statement="no layoffs")]
        ),
        ev.StakeholdersRecorded(
            metadata=_m(), stakeholders=[Stakeholder(name_or_role="CEO")]
        ),
        ev.CaseClassified(metadata=_m(), classification=cls),
        ev.CaseReclassified(metadata=_m(), classification=cls, reason="hybrid"),
        ev.InformationGapIdentified(metadata=_m(), gap=gap),
        ev.GapAnswered(
            metadata=_m(), gap_id=gap.id, question=gap.question, resolution="5%"
        ),
        ev.GapAssumed(
            metadata=_m(),
            gap_id=gap.id,
            question=gap.question,
            assumption_id=assumption.id,
        ),
        ev.AssumptionAdded(metadata=_m(), assumption=assumption),
        ev.AssumptionUpdated(
            metadata=_m(), assumption_id=assumption.id, statement="churn 6%", value="6%"
        ),
        ev.AssumptionInvalidated(
            metadata=_m(), assumption_id=assumption.id, statement="churn 6%", reason="x"
        ),
        ev.EngagementPlanCreated(metadata=_m(), plan=EngagementPlan()),
        ev.EngagementReplanned(metadata=_m(), plan=EngagementPlan(), reason="new info"),
        ev.FrameworkSelected(metadata=_m(), framework=framework),
        ev.FrameworkDeselected(
            metadata=_m(), framework_id=framework.id, name=framework.name, reason="fit"
        ),
        ev.IssueTreeGenerated(metadata=_m(), nodes=[node]),
        ev.IssueTreeNodeUpdated(
            metadata=_m(),
            node_id=node.id,
            question=node.question,
            status=node.status,
            answer="price",
        ),
        ev.KnowledgeRetrieved(
            metadata=_m(),
            references=[KnowledgeReference(kind=KnowledgeRefKind.FRAMEWORK)],
        ),
        ev.EvidenceAdded(metadata=_m(), evidence=evidence),
        ev.EvidenceValidated(
            metadata=_m(), evidence_id=evidence.id, claim=evidence.claim, validator="r"
        ),
        ev.EvidenceRejected(
            metadata=_m(), evidence_id=evidence.id, claim=evidence.claim, reason="bad"
        ),
        ev.EvidenceMarkedStale(
            metadata=_m(), evidence_id=evidence.id, claim=evidence.claim, reason="old"
        ),
        ev.SpecialistAnalysisStarted(
            metadata=_m(), analysis="financial", owner="fin", node_refs=[node.id]
        ),
        ev.FindingRecorded(
            metadata=_m(), analysis="financial", finding=Finding(question="q")
        ),
        ev.SpecialistAnalysisCompleted(
            metadata=_m(), analysis="financial", status=AnalysisStatus.COMPLETE
        ),
        ev.ReviewerReviewed(metadata=_m(), notes=ReviewerNotes()),
        ev.ReviewerApproved(metadata=_m(), summary="ok"),
        ev.ReviewerRejected(metadata=_m(), summary="rework", issues=["gap"]),
        ev.ChallengeRecorded(metadata=_m(), notes=ChallengeNotes()),
        ev.ChallengerCleared(metadata=_m(), summary="stands", caveats=["watch churn"]),
        ev.ChallengerRejected(metadata=_m(), summary="weak", counter_case="price war"),
        ev.RecommendationDrafted(
            metadata=_m(), recommendation=Recommendations(decision="cut COGS")
        ),
        ev.ConfidenceScored(metadata=_m(), report=ConfidenceReport(overall=0.7)),
        ev.RecommendationAccepted(
            metadata=_m(),
            recommendation_id="rec",
            decision="cut COGS",
            accepted_by="CEO",
        ),
        ev.ReportGenerated(metadata=_m(), deliverable=deliverable),
        ev.DeckGenerated(metadata=_m(), deliverable=deliverable),
        ev.ModelGenerated(metadata=_m(), deliverable=deliverable),
        ev.HumanInputRequested(metadata=_m(), prompt="need data", target="revenue"),
        ev.HumanInputProvided(
            metadata=_m(), prompt="need data", response="attached", provided_by="client"
        ),
        ev.PhaseTransitioned(
            metadata=_m(),
            from_status=LifecycleStatus.INTAKE,
            to_status=LifecycleStatus.ANALYSIS,
        ),
        ev.EngagementCompleted(metadata=_m(), summary="done"),
        ev.EngagementFailed(metadata=_m(), reason="n/a"),
        ev.EngagementAborted(metadata=_m(), reason="n/a", aborted_by="pm"),
        ev.LessonCaptured(metadata=_m(), lesson="mind churn"),
        ev.KnowledgeGraphLinked(
            metadata=_m(), graph_node="meridian", relationship="peer"
        ),
        ev.ProfileUpdated(metadata=_m(), company="meridian", summary="updated"),
    ]


def test_full_log_exercises_every_reducer() -> None:
    log = _full_log()
    state = project(log)
    assert state.metadata.slug == "demo"
    assert state.financial_analysis is not None
    assert len(state.deliverables) == 3
    assert len(state.quality_gates) == 4  # 2 reviewer + 2 challenger
    assert state.status is LifecycleStatus.ABORTED  # last lifecycle event wins


def test_full_log_projection_is_deterministic() -> None:
    log = _full_log()
    assert project(log) == project(log)


def test_reducers_are_noops_on_unsupported_input() -> None:
    created = ev.EngagementCreated(metadata=_m(), slug="s", tenant_id="t")
    # ProblemUpdated before any ProblemDefined -> no-op (problem stays None).
    updated = ev.ProblemUpdated(metadata=_m(), real_question="q")
    assert project([created, updated]).problem is None
    # Unknown analysis name -> no-op (no analysis block set).
    analysis_events: list[Event] = [
        ev.SpecialistAnalysisStarted(metadata=_m(), analysis="unknown", owner="o"),
        ev.FindingRecorded(
            metadata=_m(), analysis="unknown", finding=Finding(question="q")
        ),
        ev.SpecialistAnalysisCompleted(
            metadata=_m(), analysis="unknown", status=AnalysisStatus.COMPLETE
        ),
    ]
    for event in analysis_events:
        assert project([created, event]).financial_analysis is None
