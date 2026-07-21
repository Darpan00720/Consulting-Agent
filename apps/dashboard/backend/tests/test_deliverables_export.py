"""Tests for the 6-format export model."""

from __future__ import annotations

import json

from app.consulting import tracking as ctracking
from app.consulting.engine import ConsultingEngine
from app.consulting.models import (
    EngagementCategory,
    EvidenceQuality,
    EvidenceSourceType,
)
from app.deliverables.export import export_deliverable
from app.deliverables.models import (
    Audience,
    DeliverableType,
    ExportFormat,
    GeneratedDeliverable,
    GeneratedSection,
    new_deliverable_id,
)
from app.synthesis import tracking as stracking
from app.synthesis.state import SynthesisState


def _built():
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
    syn = SynthesisState(engagement_state=cstate)
    finding = stracking.create_finding(syn, "Market is large", (ev.id,), 0.8, "y")
    rec = stracking.create_recommendation(
        syn, "Enter market", "r", (finding.id,), (ev.id,)
    )
    deliverable = GeneratedDeliverable(
        id=new_deliverable_id(),
        deliverable_type=DeliverableType.EXECUTIVE_SUMMARY,
        audience=Audience.CEO,
        sections=(
            GeneratedSection(
                section_id="executive_summary",
                title="Executive Summary",
                content=(rec.statement,),
                traced_ids=(rec.id, finding.id, ev.id),
            ),
        ),
        visuals=(),
    )
    return deliverable, syn


def test_json_export_is_real_and_preserves_traceability():
    deliverable, syn = _built()
    result = export_deliverable(deliverable, syn, ExportFormat.JSON)
    assert not result.is_placeholder
    parsed = json.loads(result.content)
    assert parsed["traceability"]["recommendation_ids"]
    assert parsed["traceability"]["finding_ids"]
    assert parsed["traceability"]["evidence_ids"]


def test_markdown_export_is_real_and_contains_content():
    deliverable, syn = _built()
    result = export_deliverable(deliverable, syn, ExportFormat.MARKDOWN)
    assert not result.is_placeholder
    text = result.content.decode("utf-8")
    assert "Enter market" in text
    assert "Traceability" in text


def test_html_export_is_real_and_embeds_traceability_json():
    deliverable, syn = _built()
    result = export_deliverable(deliverable, syn, ExportFormat.HTML)
    assert not result.is_placeholder
    text = result.content.decode("utf-8")
    assert "<html>" in text
    assert "application/json" in text


def test_powerpoint_word_pdf_are_honest_placeholders_preserving_traceability():
    deliverable, syn = _built()
    for fmt in (ExportFormat.POWERPOINT, ExportFormat.WORD, ExportFormat.PDF):
        result = export_deliverable(deliverable, syn, fmt)
        assert result.is_placeholder
        payload = json.loads(result.content)
        assert payload["traceability"]["recommendation_ids"]


def test_injectable_renderer_overrides_the_placeholder():
    deliverable, syn = _built()

    def fake_renderer(d, traceability):
        return (
            f"rendered {d.id} with {len(traceability.recommendation_ids)} recs".encode()
        )

    result = export_deliverable(
        deliverable, syn, ExportFormat.POWERPOINT, renderer=fake_renderer
    )
    assert not result.is_placeholder
    assert b"rendered" in result.content


def test_content_type_reflects_the_target_format():
    deliverable, syn = _built()
    ppt = export_deliverable(deliverable, syn, ExportFormat.POWERPOINT)
    assert "presentationml" in ppt.content_type
    word = export_deliverable(deliverable, syn, ExportFormat.WORD)
    assert "wordprocessingml" in word.content_type
    pdf = export_deliverable(deliverable, syn, ExportFormat.PDF)
    assert pdf.content_type == "application/pdf"
