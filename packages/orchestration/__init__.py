"""Live-orchestration bridge (RC1.2, WI-2 / ADR-006).

Connects the deterministic ``reporting`` validation layer to the live
engagement path via a blocking report gate. See :mod:`orchestration.report_gate`.
"""

from __future__ import annotations

from orchestration.report_gate import (
    GateIssue,
    ReportGateResult,
    enforce_report_gate,
    load_state,
    run_report_gate,
)
from orchestration.telemetry import (
    content_metadata,
    instrument_gate,
    record_gate,
    record_governance,
    unsupported_finding_count,
)

__all__ = [
    "GateIssue",
    "ReportGateResult",
    "run_report_gate",
    "enforce_report_gate",
    "load_state",
    # telemetry bridge
    "instrument_gate",
    "record_gate",
    "record_governance",
    "content_metadata",
    "unsupported_finding_count",
]
