"""M1.5 baseline projection benchmarks at 10 / 100 / 1,000 / 10,000 events.

Baselines only — recorded, not optimization targets. A single measured run per
scale keeps the suite fast; optimize only if a measurement proves unacceptable.
"""

from __future__ import annotations

from typing import Any

import pytest

from state.enums import LifecycleStatus
from state.events import (
    AssumptionAdded,
    EngagementCreated,
    Event,
    EventMetadata,
    EventSource,
    EvidenceAdded,
    FrameworkSelected,
    InformationGapIdentified,
    PhaseTransitioned,
)
from state.ledgers import Assumption, Evidence, EvidenceType
from state.projection import project
from state.sections.planning import FrameworkSelection
from state.sections.scoping import Gap


def _meta() -> EventMetadata:
    return EventMetadata(
        engagement_id="eng_1", actor="system", source=EventSource.SYSTEM
    )


def _log(n: int) -> list[Event]:
    events: list[Event] = [EngagementCreated(metadata=_meta(), slug="s", tenant_id="t")]
    makers = [
        lambda: EvidenceAdded(
            metadata=_meta(),
            evidence=Evidence(claim="c", type=EvidenceType.CLIENT_FACT, confidence=0.5),
        ),
        lambda: AssumptionAdded(
            metadata=_meta(),
            assumption=Assumption(
                statement="s", value="v", rationale="r", owner="o", confidence=0.5
            ),
        ),
        lambda: InformationGapIdentified(metadata=_meta(), gap=Gap(question="q")),
        lambda: FrameworkSelected(
            metadata=_meta(), framework=FrameworkSelection(name="f")
        ),
        lambda: PhaseTransitioned(
            metadata=_meta(),
            from_status=LifecycleStatus.INTAKE,
            to_status=LifecycleStatus.ANALYSIS,
        ),
    ]
    events.extend(makers[i % len(makers)]() for i in range(n))
    return events


@pytest.mark.parametrize("n", [10, 100, 1000, 10000])
def test_projection_baseline(benchmark: Any, n: int) -> None:
    log = _log(n)
    result = benchmark.pedantic(project, args=(log,), rounds=1, iterations=1)
    assert result.projection_version >= 1
