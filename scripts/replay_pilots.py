#!/usr/bin/env python3
"""Replay the three pilot engagements as telemetry traces (v1.0 Observability).

The span data below is **reconstructed from the real pilot run logs** — the
durations, token counts, and governance verdicts actually observed when the
Northwind, Halberd, and Harbor & Vine engagements were executed (see
``docs/reviews/v1.0-Validation-Campaign.md``). Replaying them produces committed
sample JSONL traces and verifies that analytics compute correctly end-to-end.

    uv run python scripts/replay_pilots.py            # write samples + verify
    uv run python scripts/replay_pilots.py --out DIR  # custom output dir
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

_PACKAGES = Path(__file__).resolve().parent.parent / "packages"
if str(_PACKAGES) not in sys.path:
    sys.path.insert(0, str(_PACKAGES))

from telemetry import (  # noqa: E402
    EventStatus,
    JSONLSink,
    Phase,
    Recorder,
    TelemetryEvent,
    ValidationStatus,
    engagement_analytics,
)


@dataclass(frozen=True)
class SpanRecord:
    """One observed agent span (terminal event) from a real pilot run."""

    agent: str
    phase: Phase
    duration_ms: float
    status: EventStatus = EventStatus.FINISHED
    confidence: float | None = None
    frameworks_used: tuple[str, ...] = ()
    tokens: int | None = None
    validation_status: ValidationStatus | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)


def build_trace(
    engagement_id: str, spans: Sequence[SpanRecord], sink: JSONLSink
) -> list[TelemetryEvent]:
    """Emit one terminal event per observed span; return the events."""
    recorder = Recorder(sink)
    out: list[TelemetryEvent] = []
    for s in spans:
        ev = recorder.emit(
            engagement_id=engagement_id,
            agent_name=s.agent,
            phase=s.phase,
            status=s.status,
            duration_ms=s.duration_ms,
            confidence=s.confidence,
            frameworks_used=s.frameworks_used,
            tokens=s.tokens,
            validation_status=s.validation_status,
            metadata=s.metadata,
        )
        if ev is not None:
            out.append(ev)
    return out


_GATE_META = {"issue_tree_size": 3, "assumption_count": 2, "evidence_count": 0}

# Real observed durations/tokens/verdicts from the pilot runs.
PILOTS: dict[str, list[SpanRecord]] = {
    "eng_northwind_eu": [
        SpanRecord("case-classifier", Phase.CLASSIFY, 20588, tokens=8666),
        SpanRecord("information-gap", Phase.GAP_ANALYSIS, 181214, tokens=24084),
        SpanRecord("planner", Phase.PLANNING, 182109, tokens=27874),
        SpanRecord(
            "framework-selector",
            Phase.FRAMING,
            89268,
            tokens=18773,
            frameworks_used=(
                "market-attractiveness-right-to-win",
                "capital-allocation-framework",
                "build-buy-partner",
            ),
        ),
        SpanRecord("issue-tree-generator", Phase.ISSUE_TREE, 187519, tokens=37656),
        SpanRecord(
            "knowledge-agent",
            Phase.KNOWLEDGE,
            121961,
            tokens=31896,
            metadata={"hits": 6},
        ),
        SpanRecord(
            "market-analyst", Phase.ANALYSIS, 42717, confidence=0.55, tokens=10394
        ),
        SpanRecord(
            "financial-analyst", Phase.ANALYSIS, 85936, confidence=0.5, tokens=12596
        ),
        SpanRecord(
            "operations-analyst", Phase.ANALYSIS, 65419, confidence=0.55, tokens=14183
        ),
        SpanRecord(
            "strategy-analyst", Phase.ANALYSIS, 143427, confidence=0.55, tokens=26940
        ),
        SpanRecord(
            "risk-analyst", Phase.ANALYSIS, 1305038, confidence=0.5, tokens=33490
        ),
        SpanRecord(
            "reviewer",
            Phase.REVIEW,
            113584,
            tokens=25351,
            metadata={"verdict": "approved"},
        ),
        SpanRecord(
            "challenger",
            Phase.CHALLENGE,
            157318,
            tokens=30341,
            metadata={"verdict": "stands_with_caveats"},
        ),
        SpanRecord("report-writer", Phase.REPORTING, 234057, tokens=42165),
        SpanRecord(
            "report_gate",
            Phase.VALIDATION_GATE,
            1.2,
            validation_status=ValidationStatus.PASSED,
            metadata=_GATE_META,
        ),
    ],
    "eng_halberd_cost": [
        SpanRecord("case-classifier", Phase.CLASSIFY, 19573, tokens=8611),
        SpanRecord(
            "financial-analyst", Phase.ANALYSIS, 82437, confidence=0.5, tokens=11700
        ),
        SpanRecord(
            "operations-analyst", Phase.ANALYSIS, 77654, confidence=0.55, tokens=9765
        ),
        SpanRecord(
            "challenger",
            Phase.CHALLENGE,
            97275,
            tokens=16955,
            metadata={"verdict": "needs_rework"},
        ),
        SpanRecord(
            "financial-analyst",
            Phase.ANALYSIS,
            105063,
            status=EventStatus.REWORKED,
            confidence=0.5,
            tokens=13951,
            metadata={"rework_reason": "cost_base_reconcile"},
        ),
        SpanRecord(
            "challenger",
            Phase.CHALLENGE,
            90069,
            tokens=17085,
            metadata={"verdict": "stands_with_caveats"},
        ),
        SpanRecord("report-writer", Phase.REPORTING, 130331, tokens=24699),
        SpanRecord(
            "report_gate",
            Phase.VALIDATION_GATE,
            1.1,
            validation_status=ValidationStatus.PASSED,
            metadata=_GATE_META,
        ),
    ],
    "eng_harbor_vine_org": [
        SpanRecord("case-classifier", Phase.CLASSIFY, 31862, tokens=9470),
        SpanRecord(
            "framework-selector",
            Phase.FRAMING,
            62682,
            tokens=20348,
            frameworks_used=(
                "operating-model-spans-layers",
                "raci-decision-rights",
                "channel-mix-optimization",
                "mckinsey-7s",
            ),
        ),
        SpanRecord(
            "strategy-analyst", Phase.ANALYSIS, 46439, confidence=0.7, tokens=10168
        ),
        SpanRecord(
            "challenger",
            Phase.CHALLENGE,
            50883,
            tokens=13635,
            metadata={"verdict": "stands_with_caveats"},
        ),
        SpanRecord("report-writer", Phase.REPORTING, 67492, tokens=17269),
        SpanRecord(
            "report_gate",
            Phase.VALIDATION_GATE,
            0.9,
            validation_status=ValidationStatus.PASSED,
            metadata=_GATE_META,
        ),
    ],
}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Replay pilot telemetry traces.")
    parser.add_argument("--out", default="docs/observability/samples")
    args = parser.parse_args(argv)

    out = Path(args.out)
    sink = JSONLSink(root=out)
    for eid, spans in PILOTS.items():
        # fresh file each run
        target = out / f"{eid}.jsonl"
        if target.exists():
            target.unlink()
        events = build_trace(eid, spans, sink)
        a = engagement_analytics(sink.read(eid))
        assert a.event_count == len(events), "missing spans in replay"
        print(
            f"{eid}: {a.event_count} spans · "
            f"active {a.active_ms / 1000:.1f}s · "
            f"rework {a.rework_count} · frameworks {len(a.frameworks_used)}"
        )
    print(f"wrote sample traces to {out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
