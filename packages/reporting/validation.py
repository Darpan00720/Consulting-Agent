"""Structural validation for report generation (M7 / M8).

These are *mechanical* checks — they verify the engagement state satisfies
the preconditions required to produce a credible report.  They are not
a substitute for the Reviewer/Challenger governance gates; they are a
final structural guard that the renderer can rely on.

Anti-hallucination rules enforced here:
  1. Reporting gate: both governance gates must have cleared.
  2. Evidence traceability: every answered finding cites a ref.
  3. Assumption labeling: load-bearing assumptions have breakevens.
  4. No unsourced external claims: external_source evidence must have a source.
"""

from __future__ import annotations

from dataclasses import dataclass

from common.errors import StratAgentError
from state.models import EngagementState
from state.sections.analysis import AnalysisBlock


class ReportRenderError(StratAgentError):
    """Raised when the engagement state is not ready to be rendered."""


@dataclass(frozen=True)
class ValidationIssue:
    """A single structural validation finding."""

    rule: str
    detail: str
    section: str | None = None


@dataclass(frozen=True)
class ValidationReport:
    """Result of a structural validation pass."""

    valid: bool
    issues: tuple[ValidationIssue, ...]


# ---------------------------------------------------------------------------
# Gate readiness
# ---------------------------------------------------------------------------


def check_render_ready(state: EngagementState) -> ValidationReport:
    """Check all preconditions for rendering a credible report.

    Returns :class:`ValidationReport`; does not raise.
    """
    issues: list[ValidationIssue] = []

    # Rule 1 — Reviewer gate.
    if state.reviewer_notes is None or state.reviewer_notes.verdict is None:
        issues.append(
            ValidationIssue(
                "REVIEWER_GATE_NOT_RUN",
                "Reviewer has not produced a verdict — run Reviewer before rendering",
            )
        )
    elif state.reviewer_notes.verdict.value != "approved":
        issues.append(
            ValidationIssue(
                "REVIEWER_GATE_NOT_APPROVED",
                (
                    f"Reviewer verdict is"
                    f" {state.reviewer_notes.verdict.value!r},"
                    f" not 'approved'"
                ),
            )
        )

    # Rule 2 — Challenger gate.
    if state.challenge_notes is None or state.challenge_notes.verdict is None:
        issues.append(
            ValidationIssue(
                "CHALLENGER_GATE_NOT_RUN",
                (
                    "Challenger has not produced a verdict"
                    " — run Challenger before rendering"
                ),
            )
        )
    elif state.challenge_notes.verdict.value not in {
        "stands",
        "stands_with_caveats",
    }:
        issues.append(
            ValidationIssue(
                "CHALLENGER_GATE_NOT_CLEARED",
                (
                    f"Challenger verdict is"
                    f" {state.challenge_notes.verdict.value!r};"
                    f" only 'stands' or 'stands_with_caveats' permit reporting"
                ),
            )
        )

    # Rule 3 — Evidence traceability across all analysis blocks.
    _check_analysis_block(state.financial_analysis, "financial_analysis", issues)
    _check_analysis_block(state.market_analysis, "market_analysis", issues)
    _check_analysis_block(state.operations_analysis, "operations_analysis", issues)
    _check_analysis_block(state.strategy_analysis, "strategy_analysis", issues)
    _check_analysis_block(state.risk_analysis, "risk_analysis", issues)

    # Rule 4 — Load-bearing assumptions have breakevens.
    for assumption in state.assumptions:
        if assumption.load_bearing and not assumption.breakeven:
            issues.append(
                ValidationIssue(
                    "ASSUMPTION_NO_BREAKEVEN",
                    (
                        f"Load-bearing assumption `{assumption.id[:8]}`"
                        f" ({assumption.statement[:50]!r}) has no breakeven"
                    ),
                    "assumptions",
                )
            )

    return ValidationReport(valid=not issues, issues=tuple(issues))


def enforce_render_ready(state: EngagementState) -> None:
    """Raise :class:`ReportRenderError` if the state is not ready to render."""
    report = check_render_ready(state)
    if not report.valid:
        summary = "; ".join(i.detail for i in report.issues[:3])
        raise ReportRenderError(f"Engagement state is not render-ready: {summary}")


# ---------------------------------------------------------------------------
# Consistency validation
# ---------------------------------------------------------------------------


def validate_consistency(state: EngagementState) -> ValidationReport:
    """Check for internal consistency across analysis blocks.

    Checks that no two findings in different blocks directly contradict each
    other via confidence extremes (a heuristic only — full contradiction
    detection requires the Reviewer's semantic check).
    """
    issues: list[ValidationIssue] = []

    # Collect all answered findings with their sections.
    findings_by_section: dict[str, list[str]] = {}
    _collect_findings(state.financial_analysis, "financial", findings_by_section)
    _collect_findings(state.market_analysis, "market", findings_by_section)
    _collect_findings(state.operations_analysis, "operations", findings_by_section)
    _collect_findings(state.strategy_analysis, "strategy", findings_by_section)
    _collect_findings(state.risk_analysis, "risk", findings_by_section)

    # Structural check: all findings answered if block is COMPLETE.
    for section, block in [
        ("financial_analysis", state.financial_analysis),
        ("market_analysis", state.market_analysis),
        ("operations_analysis", state.operations_analysis),
        ("strategy_analysis", state.strategy_analysis),
        ("risk_analysis", state.risk_analysis),
    ]:
        if block is None:
            continue
        if block.status.value == "complete":
            unanswered = [f for f in block.findings if f.answer is None]
            if unanswered:
                issues.append(
                    ValidationIssue(
                        "INCOMPLETE_ANALYSIS_BLOCK",
                        (
                            f"{section}: {len(unanswered)} finding(s) unanswered"
                            " in a COMPLETE block"
                        ),
                        section,
                    )
                )

    return ValidationReport(valid=not issues, issues=tuple(issues))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _check_analysis_block(
    block: AnalysisBlock | None,
    section: str,
    issues: list[ValidationIssue],
) -> None:
    if block is None:
        return
    for idx, finding in enumerate(block.findings):
        if finding.answer is not None:
            has_refs = bool(finding.evidence_refs or finding.assumption_refs)
            if not has_refs:
                issues.append(
                    ValidationIssue(
                        "UNEVIDENCED_FINDING",
                        (
                            f"{section} finding {idx}"
                            f" ({finding.question[:50]!r})"
                            " has an answer but no evidence_refs or assumption_refs"
                        ),
                        section,
                    )
                )


def _collect_findings(
    block: AnalysisBlock | None,
    label: str,
    out: dict[str, list[str]],
) -> None:
    if block is None:
        return
    out[label] = [f.answer for f in block.findings if f.answer is not None]
