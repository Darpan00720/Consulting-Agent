"""Deliverable quality model (requester's "Quality Model" section) — 8
named dimensions, each a real computed score. "No deliverable may publish
without validation" is enforced by ``generator.py`` refusing to export
until ``DeliverableQualityReport.all_passed`` is true — not by convention.
"""

from __future__ import annotations

from app.deliverables.audience import profile_for
from app.deliverables.models import (
    Audience,
    DeliverableDefinition,
    DeliverableQualityCheckResult,
    DeliverableQualityDimension,
    DeliverableQualityReport,
    GeneratedDeliverable,
)
from app.synthesis.consistency import validate_consistency
from app.synthesis.models import ApprovalStatus
from app.synthesis.state import SynthesisState

_PASS_THRESHOLD = 0.6


def _traceability(
    deliverable: GeneratedDeliverable, *_a
) -> DeliverableQualityCheckResult:
    sections = deliverable.sections
    if not sections:
        return DeliverableQualityCheckResult(
            DeliverableQualityDimension.TRACEABILITY, False, 0.0, "no sections"
        )
    traced = sum(1 for s in sections if s.traced_ids)
    score = traced / len(sections)
    return DeliverableQualityCheckResult(
        DeliverableQualityDimension.TRACEABILITY,
        score >= _PASS_THRESHOLD,
        score,
        f"{traced}/{len(sections)} sections carry traceability references",
    )


def _executive_clarity(
    deliverable: GeneratedDeliverable, *_a
) -> DeliverableQualityCheckResult:
    sections = deliverable.sections
    if not sections:
        return DeliverableQualityCheckResult(
            DeliverableQualityDimension.EXECUTIVE_CLARITY, False, 0.0, "no sections"
        )
    clear = sum(1 for s in sections if s.content and s.title)
    score = clear / len(sections)
    return DeliverableQualityCheckResult(
        DeliverableQualityDimension.EXECUTIVE_CLARITY,
        score >= _PASS_THRESHOLD,
        score,
        f"{clear}/{len(sections)} sections have titled, non-empty content",
    )


def _consistency(
    deliverable: GeneratedDeliverable, _definition, state: SynthesisState, _audience
) -> DeliverableQualityCheckResult:
    blocking_types = {
        "circular_reasoning",
        "contradictory_recommendations",
        "missing_evidence",
    }
    issues = [
        i for i in validate_consistency(state) if i.issue_type.value in blocking_types
    ]
    passed = len(issues) == 0
    score = 1.0 if passed else max(0.0, 1.0 - 0.25 * len(issues))
    return DeliverableQualityCheckResult(
        DeliverableQualityDimension.CONSISTENCY,
        passed,
        score,
        f"{len(issues)} blocking consistency issue(s) in the underlying "
        "synthesis state",
    )


def _section_completeness(
    deliverable: GeneratedDeliverable, definition: DeliverableDefinition, *_a
) -> DeliverableQualityCheckResult:
    present = {s.section_id for s in deliverable.sections}
    required = set(definition.required_sections)
    if not required:
        return DeliverableQualityCheckResult(
            DeliverableQualityDimension.SECTION_COMPLETENESS,
            True,
            1.0,
            "no required sections",
        )
    covered = len(required & present)
    score = covered / len(required)
    return DeliverableQualityCheckResult(
        DeliverableQualityDimension.SECTION_COMPLETENESS,
        score >= 1.0,
        score,
        f"{covered}/{len(required)} required sections present",
    )


def _supporting_evidence(
    deliverable: GeneratedDeliverable, _definition, state: SynthesisState, *_a
) -> DeliverableQualityCheckResult:
    sections = deliverable.sections
    if not sections:
        return DeliverableQualityCheckResult(
            DeliverableQualityDimension.SUPPORTING_EVIDENCE, False, 0.0, "no sections"
        )
    evidenced = 0
    for section in sections:
        for tid in section.traced_ids:
            if tid in state.findings and state.findings[tid].supporting_evidence_ids:
                evidenced += 1
                break
            if (
                tid in state.recommendations
                and state.recommendations[tid].supporting_evidence_ids
            ):
                evidenced += 1
                break
            if tid in state.engagement_state.evidence:
                evidenced += 1
                break
    score = evidenced / len(sections)
    return DeliverableQualityCheckResult(
        DeliverableQualityDimension.SUPPORTING_EVIDENCE,
        score >= _PASS_THRESHOLD,
        score,
        f"{evidenced}/{len(sections)} sections trace to genuine evidence",
    )


def _visual_completeness(
    deliverable: GeneratedDeliverable, *_a
) -> DeliverableQualityCheckResult:
    sections = deliverable.sections
    if not sections:
        return DeliverableQualityCheckResult(
            DeliverableQualityDimension.VISUAL_COMPLETENESS, False, 0.0, "no sections"
        )
    with_visuals = sum(1 for s in sections if s.visual_ids)
    total_visuals = len(deliverable.visuals)
    score = (
        min(1.0, total_visuals / max(1, len(sections) // 3)) if total_visuals else 0.0
    )
    passed = with_visuals > 0 or total_visuals > 0
    return DeliverableQualityCheckResult(
        DeliverableQualityDimension.VISUAL_COMPLETENESS,
        passed,
        score,
        f"{total_visuals} visual(s) attached across {with_visuals} section(s)",
    )


def _audience_suitability(
    deliverable: GeneratedDeliverable, _definition, _state, audience: Audience
) -> DeliverableQualityCheckResult:
    profile = profile_for(audience)
    present = {s.section_id for s in deliverable.sections}
    covered = sum(1 for sid in profile.emphasis_sections if sid in present)
    total = len(profile.emphasis_sections) or 1
    score = covered / total
    return DeliverableQualityCheckResult(
        DeliverableQualityDimension.AUDIENCE_SUITABILITY,
        score >= _PASS_THRESHOLD,
        score,
        f"{covered}/{total} audience-emphasized sections present for {audience.value}",
    )


def _approval_status(
    deliverable: GeneratedDeliverable, _definition, state: SynthesisState, *_a
) -> DeliverableQualityCheckResult:
    referenced_rec_ids = {
        tid
        for s in deliverable.sections
        for tid in s.traced_ids
        if tid in state.recommendations
    }
    if not referenced_rec_ids:
        return DeliverableQualityCheckResult(
            DeliverableQualityDimension.APPROVAL_STATUS,
            False,
            0.0,
            "no recommendations referenced",
        )
    approved = sum(
        1
        for rid in referenced_rec_ids
        if state.recommendations[rid].approval_status is ApprovalStatus.APPROVED
    )
    score = approved / len(referenced_rec_ids)
    return DeliverableQualityCheckResult(
        DeliverableQualityDimension.APPROVAL_STATUS,
        score >= 1.0,
        score,
        f"{approved}/{len(referenced_rec_ids)} referenced recommendations are approved",
    )


_CHECKS = (
    _traceability,
    _executive_clarity,
    _consistency,
    _section_completeness,
    _supporting_evidence,
    _visual_completeness,
    _audience_suitability,
    _approval_status,
)


def assess_deliverable_quality(
    deliverable: GeneratedDeliverable,
    definition: DeliverableDefinition,
    state: SynthesisState,
    audience: Audience,
) -> DeliverableQualityReport:
    checks = tuple(
        check_fn(deliverable, definition, state, audience) for check_fn in _CHECKS
    )
    overall = sum(c.score for c in checks) / len(checks)
    return DeliverableQualityReport(checks=checks, overall_score=overall)
