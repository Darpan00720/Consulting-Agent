"""M1.2 tests for the full EngagementState aggregate (ADR-002)."""

from __future__ import annotations

from state.enums import LifecycleStatus
from state.ledgers import Evidence, EvidenceType
from state.models import EngagementMetadata, EngagementState
from state.sections.enums import CaseArchetype
from state.sections.scoping import CaseClassification, ProblemDefinition


def _meta() -> EngagementMetadata:
    return EngagementMetadata(engagement_id="eng_1", tenant_id="t_1", slug="demo")


def test_bare_state_valid_with_metadata_only() -> None:
    state = EngagementState(metadata=_meta())
    assert state.status is LifecycleStatus.INTAKE
    assert state.problem is None
    assert state.classification is None
    assert state.objectives == []
    assert state.evidence == []


def test_populated_state_round_trip() -> None:
    state = EngagementState(
        metadata=_meta(),
        problem=ProblemDefinition(raw_input="margin down"),
        classification=CaseClassification(
            primary_archetype=CaseArchetype.PROFITABILITY, confidence=0.8
        ),
        evidence=[
            Evidence(claim="rev $600M", type=EvidenceType.CLIENT_FACT, confidence=0.9)
        ],
    )
    assert EngagementState.model_validate(state.model_dump()) == state


# Every ADR-002 §3–§25 section must be present as a field on EngagementState.
ADR_002_SECTIONS = [
    "problem",
    "objectives",
    "success_criteria",
    "constraints",
    "stakeholders",
    "classification",
    "information_gaps",
    "assumptions",
    "evidence",
    "plan",
    "frameworks",
    "issue_tree",
    "knowledge_references",
    "financial_analysis",
    "market_analysis",
    "operations_analysis",
    "strategy_analysis",
    "risk_analysis",
    "reviewer_notes",
    "challenge_notes",
    "recommendations",
    "confidence",
    "deliverables",
    "knowledge_links",
]


def test_all_adr002_sections_present() -> None:
    fields = set(EngagementState.model_fields)
    missing = [section for section in ADR_002_SECTIONS if section not in fields]
    assert not missing, f"missing ADR-002 sections: {missing}"
