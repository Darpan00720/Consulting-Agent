"""Replay, parallel-execution, tracer, and CLI integration tests (Observability)."""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from telemetry import (
    EngagementTracer,
    EventStatus,
    JSONLSink,
    MemorySink,
    Phase,
    engagement_analytics,
    quality_analytics,
)

# scripts/ is not on pythonpath; add it to import the replay/CLI tools.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import engagement_telemetry  # noqa: E402
import record_telemetry  # noqa: E402
import replay_pilots  # noqa: E402

# ---------------------------------------------------------------------------
# Replay benchmark — the 3 pilots
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("eid", list(replay_pilots.PILOTS))
def test_replay_produces_complete_trace(eid: str, tmp_path: Path) -> None:
    spans = replay_pilots.PILOTS[eid]
    sink = JSONLSink(root=tmp_path)
    events = replay_pilots.build_trace(eid, spans, sink)
    reread = sink.read(eid)
    assert len(events) == len(spans)  # no missing spans
    assert len(reread) == len(spans)  # JSONL round-trips fully
    assert all(e.engagement_id == eid for e in reread)


def test_replay_durations_and_counts() -> None:
    sink = JSONLSink(root="docs/observability/samples")
    a = engagement_analytics(sink.read("eng_northwind_eu"))
    assert a.event_count == 15
    # per-phase sums equal the observed analyst durations
    assert a.duration_by_phase_ms["analysis"] == pytest.approx(
        42717 + 85936 + 65419 + 143427 + 1305038
    )
    assert a.rework_count == 0
    assert len(a.frameworks_used) == 3


def test_replay_halberd_captures_rework() -> None:
    sink = JSONLSink(root="docs/observability/samples")
    a = engagement_analytics(sink.read("eng_halberd_cost"))
    assert a.rework_count == 1  # the reconciled financial-analyst rerun


def test_dashboard_quality_metrics_across_pilots(tmp_path: Path) -> None:
    sink = JSONLSink(root=tmp_path)
    for eid, spans in replay_pilots.PILOTS.items():
        replay_pilots.build_trace(eid, spans, sink)
    q = quality_analytics(list(sink.read_all()))
    assert q.engagements == 3
    assert q.reviewer_pass_rate == 1.0  # Northwind reviewer approved (1/1)
    assert q.challenger_intervention_rate == 1.0  # all challenge verdicts intervened
    assert q.needs_rework_frequency == pytest.approx(0.2)  # 1 of 5 review+challenge
    assert "mckinsey-7s" in q.framework_selection_frequency


# ---------------------------------------------------------------------------
# Parallel execution (analysts run concurrently)
# ---------------------------------------------------------------------------


def test_parallel_spans_all_recorded_memory() -> None:
    tracer = EngagementTracer("eng_par", sink=MemorySink())

    def work(i: int) -> None:
        with tracer.agent(f"analyst-{i}", Phase.ANALYSIS) as span:
            span.set(confidence=0.5 + i / 100)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(work, range(16)))

    finished = [e for e in tracer.events() if e.status is EventStatus.FINISHED]
    assert len(finished) == 16  # every parallel span captured


def test_parallel_jsonl_append_no_loss(tmp_path: Path) -> None:
    sink = JSONLSink(root=tmp_path)
    tracer = EngagementTracer("eng_par2", sink=sink)

    def work(i: int) -> None:
        tracer.record(
            agent_name=f"a{i}", phase=Phase.ANALYSIS, status=EventStatus.FINISHED
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(work, range(20)))

    assert len(sink.read("eng_par2")) == 20  # all lines valid + present


# ---------------------------------------------------------------------------
# EngagementTracer surface
# ---------------------------------------------------------------------------


def test_tracer_rework_and_phase_marker() -> None:
    tracer = EngagementTracer("eng_t", sink=MemorySink())
    tracer.rework(agent_name="financial-analyst", phase=Phase.ANALYSIS)
    tracer.phase_marker(phase=Phase.REPORTING)
    events = tracer.events()
    assert events[0].status is EventStatus.REWORKED
    assert events[1].agent_name == "orchestrator"
    assert tracer.analytics().rework_count == 1


# ---------------------------------------------------------------------------
# CLI round-trip
# ---------------------------------------------------------------------------


def test_record_and_summarize_cli(tmp_path: Path) -> None:
    root = str(tmp_path)
    rc = record_telemetry.main(
        [
            "--engagement",
            "eng_cli",
            "--agent",
            "reviewer",
            "--phase",
            "review",
            "--status",
            "finished",
            "--duration-ms",
            "113584",
            "--meta",
            "verdict=approved",
            "--root",
            root,
        ]
    )
    assert rc == 0
    events = JSONLSink(root=tmp_path).read("eng_cli")
    assert len(events) == 1 and events[0].metadata["verdict"] == "approved"

    rc2 = engagement_telemetry.main(["--engagement", "eng_cli", "--root", root])
    assert rc2 == 0
