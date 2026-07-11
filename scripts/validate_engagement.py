#!/usr/bin/env python3
"""Live engagement validation gate (RC1.2, WI-2 / ADR-006).

Usage:
    uv run python scripts/validate_engagement.py <slug-or-path>

Resolves ``engagements/<slug>/state.json`` (or an explicit path), loads it into
an ``EngagementState``, and runs the deterministic report gate
(``enforce_render_ready`` + ``validate_consistency``). Exits 0 if the engagement
may be reported, 1 (with diagnostics) if report delivery must be blocked.

This is the runtime enforcement point that the ``solve-case`` orchestrator MUST
run in Phase 8 before accepting ``report.md`` — no report may bypass it.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Bootstrap: make the ``packages/`` source tree importable when run standalone
# (pytest/mypy set this via config; a bare ``uv run python`` does not).
_PACKAGES = Path(__file__).resolve().parent.parent / "packages"
if str(_PACKAGES) not in sys.path:
    sys.path.insert(0, str(_PACKAGES))

from orchestration.report_gate import (  # noqa: E402
    ReportGateResult,
    load_state,
    run_report_gate,
)
from reporting import ReportRenderError  # noqa: E402


def _resolve(arg: str) -> Path:
    candidate = Path(arg)
    if candidate.suffix == ".json":
        return candidate
    if candidate.is_dir():
        return candidate / "state.json"
    return Path("engagements") / arg / "state.json"


def gate_engagement(arg: str) -> ReportGateResult:
    """Load and gate the engagement named by *arg*; raises on load failure."""
    state = load_state(_resolve(arg))
    return run_report_gate(state)


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(
            "usage: validate_engagement.py <slug-or-path-to-state.json>",
            file=sys.stderr,
        )
        return 2
    try:
        result = gate_engagement(argv[0])
    except ReportRenderError as exc:
        print(f"✗ could not gate engagement: {exc}", file=sys.stderr)
        return 1
    print(result.diagnostics())
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
