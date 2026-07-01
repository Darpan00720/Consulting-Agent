"""M1.4 tests: strongly-typed id auto-generation on addressable domain models."""

from __future__ import annotations

from state.ledgers import Assumption, Evidence, EvidenceType
from state.sections.enums import DeliverableKind
from state.sections.output import Deliverable, Recommendations
from state.sections.planning import FrameworkSelection, IssueNode
from state.sections.scoping import Gap


def test_addressable_models_autogenerate_unique_ids() -> None:
    objects = [
        Evidence(claim="c", type=EvidenceType.CLIENT_FACT, confidence=0.5),
        Assumption(statement="s", value="v", rationale="r", owner="o", confidence=0.5),
        Gap(question="q"),
        IssueNode(question="q"),
        FrameworkSelection(name="Profit tree"),
        Deliverable(kind=DeliverableKind.REPORT),
        Recommendations(),
    ]
    ids = [obj.id for obj in objects]
    assert all(ids), "every addressable model auto-populates its id"
    assert len(set(ids)) == len(ids), "ids are unique, not order-derived"
