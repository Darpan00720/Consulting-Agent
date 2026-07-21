"""Tests for the deliverable generator — "no deliverable may publish
without validation" as a real, enforced gate."""

from __future__ import annotations

import dataclasses

import pytest

from app.consulting import tracking as ctracking
from app.consulting.engine import ConsultingEngine
from app.consulting.models import (
    EngagementCategory,
    EvidenceQuality,
    EvidenceSourceType,
)
from app.deliverables.errors import QualityValidationFailedError
from app.deliverables.generator import (
    export_validated_deliverable,
    generate_deliverable,
)
from app.deliverables.models import (
    Audience,
    DeliverableType,
    ExportFormat,
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


def test_generate_deliverable_produces_required_sections():
    syn, ev = _synthesis_state()
    finding = stracking.create_finding(syn, "x", (ev.id,), 0.8, "y")
    stracking.create_recommendation(syn, "s", "r", (finding.id,), (ev.id,))
    deliverable = generate_deliverable(
        DeliverableType.EXECUTIVE_SUMMARY, syn, Audience.CEO
    )
    section_ids = {s.section_id for s in deliverable.sections}
    assert {"executive_summary", "key_findings", "recommendations"} <= section_ids


def test_export_without_quality_pass_raises():
    syn, ev = _synthesis_state()
    finding = stracking.create_finding(syn, "x", (ev.id,), 0.8, "y")
    stracking.create_recommendation(syn, "s", "r", (finding.id,), (ev.id,))
    deliverable = generate_deliverable(
        DeliverableType.EXECUTIVE_SUMMARY, syn, Audience.CEO
    )
    assert not deliverable.quality_report.all_passed  # unapproved + no visuals
    with pytest.raises(QualityValidationFailedError):
        export_validated_deliverable(deliverable, syn, ExportFormat.JSON)


def test_export_succeeds_once_quality_passes():
    syn, ev = _synthesis_state()
    finding = stracking.create_finding(syn, "x", (ev.id,), 0.8, "y")
    rec = stracking.create_recommendation(syn, "s", "r", (finding.id,), (ev.id,))
    syn.recommendations[rec.id] = dataclasses.replace(
        rec, approval_status=ApprovalStatus.APPROVED
    )
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
    assert deliverable.quality_report.all_passed
    result = export_validated_deliverable(deliverable, syn, ExportFormat.JSON)
    assert not result.is_placeholder


def test_generated_sections_are_reordered_for_the_requested_audience():
    from app.synthesis.models import TradeOffOption
    from app.synthesis.tradeoff import compare_options

    syn, ev = _synthesis_state()
    finding = stracking.create_finding(syn, "x", (ev.id,), 0.8, "y")
    stracking.create_recommendation(
        syn,
        "s",
        "r",
        (finding.id,),
        (ev.id,),
        cost="$1M",
        risk="market risk",
        trade_offs=("slower payback",),
        kpis=("ARR",),
        expected_benefits=("growth",),
    )
    options = (
        TradeOffOption(id="a", name="Option A", dimension_scores={"financial": 8}),
        TradeOffOption(id="b", name="Option B", dimension_scores={"financial": 3}),
    )
    trade_off_result = compare_options(options, dimension_weights={"financial": 1.0})
    deliverable = generate_deliverable(
        DeliverableType.BUSINESS_CASE,
        syn,
        Audience.CFO,
        trade_off_result=trade_off_result,
    )
    section_ids = [s.section_id for s in deliverable.sections]
    # CFO emphasizes business_case first
    assert section_ids[0] == "business_case"


def test_include_optional_sections_are_added_when_requested():
    syn, ev = _synthesis_state()
    finding = stracking.create_finding(syn, "x", (ev.id,), 0.8, "y")
    stracking.create_recommendation(
        syn, "s", "r", (finding.id,), (ev.id,), risk="market risk"
    )
    deliverable = generate_deliverable(
        DeliverableType.EXECUTIVE_SUMMARY,
        syn,
        Audience.CEO,
        include_optional_sections=("risk_assessment",),
    )
    section_ids = {s.section_id for s in deliverable.sections}
    assert "risk_assessment" in section_ids
