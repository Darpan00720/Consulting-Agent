"""Live report-validation gate (RC1.2, WI-2 / ADR-006).

Bridges the deterministic ``reporting`` validation layer onto the live
engagement path. The live orchestrator emits a structured ``state.json`` for a
finished engagement; this module loads it into an :class:`EngagementState` and
runs the deterministic anti-hallucination gate BEFORE a report may be delivered.

The gate combines both structural checks:
  * ``reporting.check_render_ready`` — governance gates cleared, findings
    evidenced, load-bearing assumptions have breakevens;
  * ``reporting.validate_consistency`` — no COMPLETE analysis block has an
    unanswered finding.

On failure the gate BLOCKS (``enforce_report_gate`` raises) and yields
actionable, human-readable diagnostics. Nothing here mutates state.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from reporting import (
    ReportRenderError,
    check_render_ready,
    validate_consistency,
)
from state.models import EngagementState


@dataclass(frozen=True)
class GateIssue:
    """One blocking finding, tagged by which check produced it."""

    check: str  # "render_ready" | "consistency"
    rule: str
    detail: str
    section: str | None = None

    def render(self) -> str:
        loc = f" [{self.section}]" if self.section else ""
        return f"  ✗ ({self.check}:{self.rule}){loc} {self.detail}"


@dataclass(frozen=True)
class ReportGateResult:
    """Combined outcome of the live report gate."""

    slug: str
    render_ready: bool
    consistent: bool
    issues: tuple[GateIssue, ...]

    @property
    def ok(self) -> bool:
        return self.render_ready and self.consistent

    def diagnostics(self) -> str:
        """A multi-line, actionable diagnostic block."""
        if self.ok:
            return (
                f"✓ report gate PASSED for {self.slug!r} — "
                "render-ready and internally consistent."
            )
        header = (
            f"✗ report gate BLOCKED for {self.slug!r}: "
            f"{len(self.issues)} issue(s). Report delivery is not permitted."
        )
        return "\n".join([header, *(i.render() for i in self.issues)])


def run_report_gate(state: EngagementState) -> ReportGateResult:
    """Run the full deterministic gate on *state*; never raises for gate failure."""
    rr = check_render_ready(state)
    vc = validate_consistency(state)
    issues: list[GateIssue] = [
        GateIssue("render_ready", i.rule, i.detail, i.section) for i in rr.issues
    ]
    issues += [GateIssue("consistency", i.rule, i.detail, i.section) for i in vc.issues]
    return ReportGateResult(
        slug=state.metadata.slug,
        render_ready=rr.valid,
        consistent=vc.valid,
        issues=tuple(issues),
    )


def enforce_report_gate(state: EngagementState) -> ReportGateResult:
    """Run the gate and RAISE :class:`ReportRenderError` if it does not pass.

    Returns the (passing) result on success so callers can log it.
    """
    result = run_report_gate(state)
    if not result.ok:
        raise ReportRenderError(result.diagnostics())
    return result


def load_state(path: Path) -> EngagementState:
    """Load and validate an ``EngagementState`` from a ``state.json`` file.

    Raises :class:`ReportRenderError` with an actionable message if the file is
    missing or does not conform to the state schema.
    """
    if not path.is_file():
        raise ReportRenderError(f"state file not found: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReportRenderError(f"cannot read state file {path}: {exc}") from exc
    try:
        return EngagementState.model_validate(raw)
    except Exception as exc:  # noqa: BLE001 — surface any pydantic error uniformly
        raise ReportRenderError(
            f"state.json does not conform to the EngagementState schema: {exc}"
        ) from exc
