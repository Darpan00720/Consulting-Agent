"""M1.7.7 baselines: append path, snapshot, and replay verification.

Regression references only — recorded, never optimization targets, never
latency assertions (the standing policy since M1.5). Single measured cold run
per scale (`pedantic`, rounds=1, iterations=1), consistent with the projection
and validation baselines. Fixtures build a realistic state by appending an
`EngagementCreated`-led log through the real pipeline, so the benchmarked
state is genuine and the builder is shared (not duplicated per benchmark).

The plain (non-benchmark) tests at the end verify the *fixture infrastructure*
— they assert shape/validity, never timing.
"""

from __future__ import annotations

from typing import Any

import pytest

from state import Engagement, Evidence, EvidenceType
from state.append import AppendPipeline, verify_log, verify_pair
from state.events import (
    EngagementCreated,
    Event,
    EventMetadata,
    EventSource,
    EvidenceAdded,
)
from state.models import EngagementMetadata, EngagementState
from state.projection import project

_SCALES = [10, 100, 1000, 10000]
_BATCH_SCALES = [10, 100, 1000]


def _meta(**kwargs: Any) -> EventMetadata:
    base: dict[str, Any] = {
        "engagement_id": "eng_1",
        "actor": "system",
        "source": EventSource.SYSTEM,
    }
    base.update(kwargs)
    return EventMetadata(**base)


def _created() -> EngagementCreated:
    return EngagementCreated(metadata=_meta(), slug="demo", tenant_id="t_1")


def _evidence(claim: str = "c") -> EvidenceAdded:
    ev = Evidence(claim=claim, type=EvidenceType.CLIENT_FACT, confidence=0.5)
    return EvidenceAdded(metadata=_meta(), evidence=ev)


def _engagement_of_size(n: int) -> Engagement:
    """An append-capable engagement whose committed log has ``n`` events.

    The log is genesis-led (EngagementCreated first), so it is also a valid
    input to the replay checker.
    """
    engagement = Engagement.create(engagement_id="eng_1", tenant_id="t_1", slug="demo")
    events: list[Event] = [_created()]
    events += [_evidence(f"c{i}") for i in range(1, n)]
    engagement.append_events(events, expected_version=0)
    return engagement


def _log_of_size(n: int) -> tuple[Event, ...]:
    """A genesis-led committed log of ``n`` events.

    Built via the pipeline directly: the facade intentionally does not expose
    the committed log (it serializes state only), so the log fixture uses the
    internal AppendPipeline — as the pipeline tests do.
    """
    meta = EngagementMetadata(engagement_id="eng_1", tenant_id="t_1", slug="demo")
    pipeline = AppendPipeline(EngagementState(metadata=meta))
    events: list[Event] = [_created()]
    events += [_evidence(f"c{i}") for i in range(1, n)]
    pipeline.append_events(events, expected_version=0)
    return pipeline.committed().log


# --- benchmarks --------------------------------------------------------------


@pytest.mark.parametrize("size", _SCALES)
def test_append_event_baseline(benchmark: Any, size: int) -> None:
    engagement = _engagement_of_size(size)
    version = engagement.current_version()
    event = _evidence("appended")
    result = benchmark.pedantic(
        engagement.append_event,
        args=(event,),
        kwargs={"expected_version": version},
        rounds=1,
        iterations=1,
    )
    assert result.success


@pytest.mark.parametrize("batch", _BATCH_SCALES)
def test_append_events_baseline(benchmark: Any, batch: int) -> None:
    engagement = _engagement_of_size(1)  # genesis only, version 1
    events = [_evidence(f"b{i}") for i in range(batch)]
    result = benchmark.pedantic(
        engagement.append_events,
        args=(events,),
        kwargs={"expected_version": 1},
        rounds=1,
        iterations=1,
    )
    assert result.appended == batch


@pytest.mark.parametrize("size", _SCALES)
def test_get_state_baseline(benchmark: Any, size: int) -> None:
    engagement = _engagement_of_size(size)
    state = benchmark.pedantic(engagement.get_state, rounds=1, iterations=1)
    assert state.metadata.state_version == size


@pytest.mark.parametrize("size", _SCALES)
def test_verify_log_baseline(benchmark: Any, size: int) -> None:
    log = _log_of_size(size)
    benchmark.pedantic(verify_log, args=(log,), rounds=1, iterations=1)


@pytest.mark.parametrize("size", _SCALES)
def test_verify_pair_baseline(benchmark: Any, size: int) -> None:
    log = _log_of_size(size)
    snapshot = project(list(log))
    benchmark.pedantic(verify_pair, args=(log, snapshot), rounds=1, iterations=1)


# --- fixture-infrastructure tests (shape/validity only, never timing) --------


def test_fixture_builder_is_valid_and_sized() -> None:
    engagement = _engagement_of_size(10)
    assert engagement.current_version() == 10
    assert engagement.get_state().metadata.state_version == 10
    log = _log_of_size(10)
    assert len(log) == 10
    assert isinstance(log[0], EngagementCreated)
    verify_log(log)  # genesis-led, contiguous, unique
    verify_pair(log, project(list(log)))  # canonical pair passes


def test_batch_fixture_is_genesis_only() -> None:
    engagement = _engagement_of_size(1)
    assert engagement.current_version() == 1
    assert len(_log_of_size(1)) == 1
