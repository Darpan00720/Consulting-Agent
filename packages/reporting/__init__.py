"""Reporting capability — report rendering and structural validation."""

from __future__ import annotations

from reporting.renderer import render_report
from reporting.validation import (
    ReportRenderError,
    ValidationIssue,
    ValidationReport,
    check_render_ready,
    enforce_render_ready,
    validate_consistency,
)
from state.models import EngagementState


def engagement_summary(state: EngagementState) -> dict[str, object]:
    """Return a lightweight summary dict of the engagement for report generation."""
    return {
        "engagement_id": state.metadata.engagement_id,
        "tenant_id": state.metadata.tenant_id,
        "slug": state.metadata.slug,
        "status": state.status.value,
        "real_question": (
            state.problem.real_question if state.problem else None
        ),
        "archetype": (
            state.classification.primary_archetype.value
            if state.classification
            else None
        ),
        "frameworks": [f.name for f in state.frameworks],
        "leaf_count": sum(
            1
            for n in state.issue_tree
            if n.id
            not in {p.parent for p in state.issue_tree if p.parent is not None}
        ),
        "reviewer_verdict": (
            state.reviewer_notes.verdict.value
            if state.reviewer_notes and state.reviewer_notes.verdict
            else None
        ),
        "challenger_verdict": (
            state.challenge_notes.verdict.value
            if state.challenge_notes and state.challenge_notes.verdict
            else None
        ),
    }


__all__ = [
    "ReportRenderError",
    "ValidationIssue",
    "ValidationReport",
    "check_render_ready",
    "enforce_render_ready",
    "engagement_summary",
    "render_report",
    "validate_consistency",
]
