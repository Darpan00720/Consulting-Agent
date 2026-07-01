"""Strongly-typed identifiers for addressable domain objects and events.

Each is a distinct value object (``NewType`` over ``str``): the same runtime
representation, but not interchangeable at type-check time. This gives one
identifier system shared by the domain models and the event references, so no
conversion code is needed between the two layers. The generic ``Identifier`` in
``common.values`` remains the base type for embedded/nested records that are never
referenced by id.
"""

from __future__ import annotations

from typing import NewType

from common.values import new_id

EventId = NewType("EventId", str)
EngagementId = NewType("EngagementId", str)
AssumptionId = NewType("AssumptionId", str)
EvidenceId = NewType("EvidenceId", str)
GapId = NewType("GapId", str)
IssueNodeId = NewType("IssueNodeId", str)
FrameworkId = NewType("FrameworkId", str)
DeliverableId = NewType("DeliverableId", str)
RecommendationId = NewType("RecommendationId", str)


def new_event_id() -> EventId:
    return EventId(new_id())


def new_assumption_id() -> AssumptionId:
    return AssumptionId(new_id())


def new_evidence_id() -> EvidenceId:
    return EvidenceId(new_id())


def new_gap_id() -> GapId:
    return GapId(new_id())


def new_issue_node_id() -> IssueNodeId:
    return IssueNodeId(new_id())


def new_framework_id() -> FrameworkId:
    return FrameworkId(new_id())


def new_deliverable_id() -> DeliverableId:
    return DeliverableId(new_id())


def new_recommendation_id() -> RecommendationId:
    return RecommendationId(new_id())
