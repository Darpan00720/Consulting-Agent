"""Tests for the 8-dimension deliverable quality model."""

from __future__ import annotations

import dataclasses

from app.consulting import tracking as ctracking
from app.consulting.engine import ConsultingEngine
from app.consulting.models import (
    EngagementCategory,
    EvidenceQuality,
    EvidenceSourceType,
)
from app.deliverables.generator import generate_deliverable
from app.deliverables.models import (
    Audience,
    DeliverableQualityDimension,
    DeliverableType,
    VisualSpec,
    VisualType,
    new_visual_id,
)
from app.synthesis import tracking as stracking
from app.synthesis.models import ApprovalStatus
from app.synthesis.state import SynthesisState


def _synthesis_state():
    engine = ConsultingEngine()
    cstate = engine.start_engagement(
        "e1", EngagementCategory.MARKET_ENTRY, trace_id="t1"
    )
    ev = ctracking.add_evidence(
        cstate,
        "report",
        EvidenceSourceType.EXTERNAL_RESEARCH,
        EvidenceQuality.HIGH,
        0.8,
        "x",
    )
    return SynthesisState(engagement_state=cstate), ev


def test_quality_report_has_all_8_dimensions():
    syn, ev = _synthesis_state()
    finding = stracking.create_finding(syn, "x", (ev.id,), 0.8, "y")
    stracking.create_recommendation(syn, "s", "r", (finding.id,), (ev.id,))
    deliverable = generate_deliverable(
        DeliverableType.EXECUTIVE_SUMMARY, syn, Audience.CEO
    )
    assert len(deliverable.quality_report.checks) == 8
    dims = {c.dimension for c in deliverable.quality_report.checks}
    assert dims == set(DeliverableQualityDimension)


def test_unapproved_recommendation_fails_approval_status_check():
    syn, ev = _synthesis_state()
    finding = stracking.create_finding(syn, "x", (ev.id,), 0.8, "y")
    stracking.create_recommendation(syn, "s", "r", (finding.id,), (ev.id,))
    deliverable = generate_deliverable(
        DeliverableType.EXECUTIVE_SUMMARY, syn, Audience.CEO
    )
    by_dim = {c.dimension: c for c in deliverable.quality_report.checks}
    assert not by_dim[DeliverableQualityDimension.APPROVAL_STATUS].passed


def test_approved_recommendation_passes_approval_status_check():
    syn, ev = _synthesis_state()
    finding = stracking.create_finding(syn, "x", (ev.id,), 0.8, "y")
    rec = stracking.create_recommendation(syn, "s", "r", (finding.id,), (ev.id,))
    syn.recommendations[rec.id] = dataclasses.replace(
        rec, approval_status=ApprovalStatus.APPROVED
    )
    deliverable = generate_deliverable(
        DeliverableType.EXECUTIVE_SUMMARY, syn, Audience.CEO
    )
    by_dim = {c.dimension: c for c in deliverable.quality_report.checks}
    assert by_dim[DeliverableQualityDimension.APPROVAL_STATUS].passed


def test_no_visuals_fails_visual_completeness_check():
    syn, ev = _synthesis_state()
    finding = stracking.create_finding(syn, "x", (ev.id,), 0.8, "y")
    stracking.create_recommendation(syn, "s", "r", (finding.id,), (ev.id,))
    deliverable = generate_deliverable(
        DeliverableType.EXECUTIVE_SUMMARY, syn, Audience.CEO
    )
    by_dim = {c.dimension: c for c in deliverable.quality_report.checks}
    assert not by_dim[DeliverableQualityDimension.VISUAL_COMPLETENESS].passed


def test_visuals_pass_visual_completeness_check():
    syn, ev = _synthesis_state()
    finding = stracking.create_finding(syn, "x", (ev.id,), 0.8, "y")
    stracking.create_recommendation(syn, "s", "r", (finding.id,), (ev.id,))
    visual = VisualSpec(
        id=new_visual_id(),
        visual_type=VisualType.CHART,
        title="t",
        data_refs=(),
        data={},
    )
    deliverable = generate_deliverable(
        DeliverableType.EXECUTIVE_SUMMARY,
        syn,
        Audience.CEO,
        visuals=(visual,),
        section_visual_ids={"executive_summary": (visual.id,)},
    )
    by_dim = {c.dimension: c for c in deliverable.quality_report.checks}
    assert by_dim[DeliverableQualityDimension.VISUAL_COMPLETENESS].passed


def test_missing_required_section_fails_section_completeness():
    """Simulate a deliverable object built without one of its required
    sections (bypassing the generator) to prove the check is real."""
    from app.deliverables.quality import assess_deliverable_quality
    from app.deliverables.registry import default_deliverable_registry

    syn, ev = _synthesis_state()
    finding = stracking.create_finding(syn, "x", (ev.id,), 0.8, "y")
    stracking.create_recommendation(syn, "s", "r", (finding.id,), (ev.id,))
    deliverable = generate_deliverable(
        DeliverableType.EXECUTIVE_SUMMARY, syn, Audience.CEO
    )
    truncated = dataclasses.replace(deliverable, sections=deliverable.sections[:1])
    definition = default_deliverable_registry().get("executive_summary")
    report = assess_deliverable_quality(truncated, definition, syn, Audience.CEO)
    by_dim = {c.dimension: c for c in report.checks}
    assert not by_dim[DeliverableQualityDimension.SECTION_COMPLETENESS].passed
