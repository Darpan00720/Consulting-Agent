"""Telemetry layer tests (v1.0 Observability)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from telemetry import (
    EventStatus,
    JSONLSink,
    MemorySink,
    MultiSink,
    NullSink,
    Phase,
    Recorder,
    TelemetryEvent,
    ValidationStatus,
    engagement_analytics,
    quality_analytics,
    summarize_confidence,
)
from telemetry.recorder import default_redactor


def _ev(**kw: object) -> TelemetryEvent:
    base: dict[str, object] = {
        "engagement_id": "eng_1",
        "agent_name": "financial-analyst",
        "phase": Phase.ANALYSIS,
        "status": EventStatus.FINISHED,
    }
    base.update(kw)
    return TelemetryEvent(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Event schema
# ---------------------------------------------------------------------------


def test_event_is_frozen_and_strict() -> None:
    e = _ev()
    with pytest.raises(ValidationError):
        e.status = EventStatus.FAILED  # type: ignore[misc]
    with pytest.raises(ValidationError):
        TelemetryEvent(  # extra field forbidden
            engagement_id="e",
            agent_name="a",
            phase=Phase.ANALYSIS,
            status=EventStatus.FINISHED,
            bogus=1,  # type: ignore[call-arg]
        )


def test_event_has_all_spec_fields() -> None:
    e = _ev(
        duration_ms=12.5,
        confidence=0.8,
        frameworks_used=("profit-tree",),
        tokens=1500,
        retry_count=1,
        validation_status=ValidationStatus.PASSED,
        metadata={"k": "v"},
    )
    for f in (
        "timestamp",
        "engagement_id",
        "agent_name",
        "phase",
        "duration_ms",
        "status",
        "confidence",
        "frameworks_used",
        "tokens",
        "retry_count",
        "validation_status",
        "metadata",
    ):
        assert hasattr(e, f)


def test_to_otlp_shape() -> None:
    e = _ev(duration_ms=500.0, confidence=0.9, status=EventStatus.FAILED)
    span = e.to_otlp()
    assert span["trace_id"] == "eng_1"
    assert span["span_id"] == e.event_id
    assert span["name"] == "financial-analyst:analysis"
    assert span["status"]["code"] == "ERROR"
    assert span["attributes"]["stratagent.confidence"] == 0.9
    assert span["end_time_unix_nano"] > span["start_time_unix_nano"]


def test_json_roundtrip() -> None:
    e = _ev(confidence=0.7, frameworks_used=("a", "b"))
    restored = TelemetryEvent.model_validate_json(e.model_dump_json())
    assert restored == e


# ---------------------------------------------------------------------------
# Sinks
# ---------------------------------------------------------------------------


def test_jsonl_sink_append_and_read(tmp_path: Path) -> None:
    sink = JSONLSink(root=tmp_path)
    sink.emit(_ev())
    sink.emit(_ev(status=EventStatus.STARTED))
    loaded = sink.read("eng_1")
    assert len(loaded) == 2  # append-only, both preserved
    assert (tmp_path / "eng_1.jsonl").read_text().count("\n") == 2


def test_jsonl_sink_read_all_across_engagements(tmp_path: Path) -> None:
    sink = JSONLSink(root=tmp_path)
    sink.emit(_ev(engagement_id="eng_a"))
    sink.emit(_ev(engagement_id="eng_b"))
    assert {e.engagement_id for e in sink.read_all()} == {"eng_a", "eng_b"}


def test_jsonl_sink_path_is_escape_safe(tmp_path: Path) -> None:
    sink = JSONLSink(root=tmp_path)
    sink.emit(_ev(engagement_id="../../etc/passwd"))
    # no file written outside root
    assert not (tmp_path.parent / "etc").exists()
    files = list(tmp_path.glob("*.jsonl"))
    assert len(files) == 1


def test_memory_and_null_sinks() -> None:
    mem = MemorySink()
    mem.emit(_ev())
    assert len(mem.events) == 1
    null = NullSink()
    null.emit(_ev())  # no-op, no error


def test_multisink_isolates_failure() -> None:
    class _BadSink:
        def emit(self, event: TelemetryEvent) -> None:
            raise RuntimeError("boom")

        def close(self) -> None:
            return None

    mem = MemorySink()
    multi = MultiSink([_BadSink(), mem])
    multi.emit(_ev())  # bad sink fails, mem still gets it
    assert len(mem.events) == 1


# ---------------------------------------------------------------------------
# Recorder
# ---------------------------------------------------------------------------


def test_recorder_emit_records_to_sink() -> None:
    rec = Recorder(MemorySink())
    out = rec.emit(
        engagement_id="e",
        agent_name="reviewer",
        phase=Phase.REVIEW,
        status=EventStatus.FINISHED,
    )
    assert out is not None
    assert len(rec.sink.events) == 1  # type: ignore[attr-defined]


def test_span_times_and_emits_start_finish() -> None:
    clock = iter([0.0, 0.5]).__next__
    rec = Recorder(MemorySink(), clock=clock)
    with rec.span(
        engagement_id="e", agent_name="market-analyst", phase=Phase.ANALYSIS
    ) as span:
        span.set(confidence=0.75, frameworks_used=["tam-sam-som"])
    events = rec.sink.events  # type: ignore[attr-defined]
    assert [e.status for e in events] == [EventStatus.STARTED, EventStatus.FINISHED]
    finished = events[1]
    assert finished.duration_ms == pytest.approx(500.0)
    assert finished.confidence == 0.75
    assert finished.frameworks_used == ("tam-sam-som",)


def test_span_records_failure_and_reraises() -> None:
    rec = Recorder(MemorySink())
    with (
        pytest.raises(ValueError),
        rec.span(engagement_id="e", agent_name="a", phase=Phase.ANALYSIS),
    ):
        raise ValueError("nope")
    events = rec.sink.events  # type: ignore[attr-defined]
    assert events[-1].status is EventStatus.FAILED


def test_sampling_drops() -> None:
    rec = Recorder(MemorySink(), sample_rate=0.0)
    assert (
        rec.emit(
            engagement_id="e",
            agent_name="a",
            phase=Phase.ANALYSIS,
            status=EventStatus.FINISHED,
        )
        is None
    )
    assert len(rec.sink.events) == 0  # type: ignore[attr-defined]


def test_sampling_keeps_when_under_rate() -> None:
    rec = Recorder(MemorySink(), sample_rate=0.5, sampler=lambda: 0.1)
    assert (
        rec.emit(
            engagement_id="e",
            agent_name="a",
            phase=Phase.ANALYSIS,
            status=EventStatus.FINISHED,
        )
        is not None
    )


def test_invalid_sample_rate() -> None:
    with pytest.raises(ValueError):
        Recorder(sample_rate=1.5)


def test_redaction() -> None:
    out = default_redactor(
        {"_private": "secret", "long": "x" * 999, "n": 3, "nested": {"a": 1}}
    )
    assert "_private" not in out  # underscore keys dropped
    assert len(out["long"]) == 256  # truncated
    assert out["n"] == 3
    assert "nested" not in out  # nested mappings dropped


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


def test_engagement_analytics() -> None:
    events = [
        _ev(phase=Phase.PLANNING, duration_ms=100.0),
        _ev(phase=Phase.ANALYSIS, duration_ms=300.0),
        _ev(phase=Phase.ANALYSIS, duration_ms=200.0),
        _ev(phase=Phase.CHALLENGE, status=EventStatus.REWORKED),
        _ev(phase=Phase.VALIDATION_GATE, validation_status=ValidationStatus.BLOCKED),
        _ev(phase=Phase.KNOWLEDGE, metadata={"hits": 4}),
        _ev(confidence=0.9, frameworks_used=("profit-tree",)),
        _ev(metadata={"issue_tree_size": 10, "recommendation_count": 2}),
    ]
    a = engagement_analytics(events)
    assert a.duration_by_phase_ms["analysis"] == 500.0
    assert a.rework_count == 1
    assert a.validation_failures == 1
    assert a.knowledge_retrieval_hits == 4
    assert "profit-tree" in a.frameworks_used
    assert a.issue_tree_size == 10
    assert a.recommendation_count == 2
    assert a.confidence.n == 1


def test_quality_analytics() -> None:
    events = [
        _ev(phase=Phase.REVIEW, metadata={"verdict": "approved"}),
        _ev(
            phase=Phase.REVIEW, engagement_id="e2", metadata={"verdict": "needs_rework"}
        ),
        _ev(phase=Phase.CHALLENGE, metadata={"verdict": "stands_with_caveats"}),
        _ev(phase=Phase.CHALLENGE, engagement_id="e2", metadata={"verdict": "stands"}),
        _ev(phase=Phase.VALIDATION_GATE, validation_status=ValidationStatus.BLOCKED),
        _ev(phase=Phase.VALIDATION_GATE, validation_status=ValidationStatus.PASSED),
        _ev(phase=Phase.KNOWLEDGE, metadata={"hits": 3}),
        _ev(frameworks_used=("profit-tree", "tam-sam-som")),
        _ev(metadata={"assumption_count": 5, "unsupported_finding_count": 0}),
    ]
    q = quality_analytics(events)
    assert q.reviewer_pass_rate == pytest.approx(0.5)  # 1 approved of 2
    assert q.challenger_intervention_rate == pytest.approx(0.5)  # 1 caveat of 2
    assert q.needs_rework_frequency == pytest.approx(0.25)  # 1 of 4 review+challenge
    assert q.validation_block_rate == pytest.approx(0.5)
    assert q.framework_selection_frequency["profit-tree"] == 1
    assert q.knowledge_retrieval_effectiveness == 1.0
    assert q.assumption_count_total == 5


def test_summarize_confidence_buckets_and_empty() -> None:
    s = summarize_confidence([0.4, 0.6, 0.8, 0.95])
    assert s.n == 4
    assert s.buckets["0.0-0.5"] == 1
    assert s.buckets["0.9-1.0"] == 1
    empty = summarize_confidence([])
    assert empty.n == 0 and empty.mean is None


def test_engagement_analytics_empty() -> None:
    a = engagement_analytics([])
    assert a.event_count == 0 and a.total_wall_ms == 0.0


def test_close_is_noop_everywhere(tmp_path: Path) -> None:
    for sink in (MemorySink(), NullSink(), JSONLSink(root=tmp_path)):
        sink.close()  # idempotent no-ops
    MultiSink([MemorySink()]).close()
    Recorder(MemorySink()).sink.close()


def test_jsonl_read_missing_returns_empty(tmp_path: Path) -> None:
    assert JSONLSink(root=tmp_path).read("nope") == []
    assert list(JSONLSink(root=tmp_path / "absent").read_all()) == []


def test_redactor_truncates_list_values() -> None:
    out = default_redactor({"items": ["a" * 999, "b"], "big": list(range(50))})
    assert len(out["items"][0]) == 256
    assert len(out["big"]) == 20  # list capped
