"""M1.2 tests: section-model ids, audit metadata, value objects, and enum defaults."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from state.sections.enums import (
    CaseArchetype,
    ConstraintType,
    DeliverableKind,
    KnowledgeRefKind,
    StakeholderRelationship,
)
from state.sections.output import ConfidenceReport, Deliverable
from state.sections.planning import IssueNode
from state.sections.scoping import (
    CaseClassification,
    Constraint,
    ProblemDefinition,
    Stakeholder,
)


def test_domain_object_auto_id_present_and_unique() -> None:
    a = ProblemDefinition(raw_input="x")
    b = ProblemDefinition(raw_input="y")
    assert a.id and b.id
    assert a.id != b.id  # unique, not derived from ordering


def test_domain_object_id_is_immutable() -> None:
    node = IssueNode(question="Why did margin fall?")
    with pytest.raises(ValidationError):
        node.id = "changed"  # frozen


def test_audit_fields_default_to_none() -> None:
    node = IssueNode(question="q")
    assert node.created_at is None
    assert node.updated_at is None
    assert node.created_by is None
    assert node.updated_by is None


def test_confidence_score_reused_and_bounded() -> None:
    CaseClassification(primary_archetype=CaseArchetype.PROFITABILITY, confidence=0.8)
    with pytest.raises(ValidationError):
        CaseClassification(
            primary_archetype=CaseArchetype.PROFITABILITY, confidence=1.5
        )


def test_confidence_report_overall_bounded() -> None:
    ConfidenceReport(overall=0.5)
    with pytest.raises(ValidationError):
        ConfidenceReport(overall=2.0)


def test_enum_defaults_and_extensibility() -> None:
    assert Constraint(statement="no layoffs").type is ConstraintType.OTHER
    assert Stakeholder(name_or_role="CEO").relationship is StakeholderRelationship.OTHER
    assert "unknown" in {a.value for a in CaseArchetype}
    assert "other" in {k.value for k in KnowledgeRefKind}
    assert "other" in {k.value for k in DeliverableKind}


def test_section_construction_smoke() -> None:
    Deliverable(kind=DeliverableKind.REPORT)
    ProblemDefinition(raw_input="A grocery chain's margin fell from 4% to 1.5%.")
