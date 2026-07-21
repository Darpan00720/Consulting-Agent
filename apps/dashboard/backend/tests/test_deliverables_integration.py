"""Integration tests: the Deliverables Engine wired against REAL W7
(ConsultingEngine), W10 (Synthesis Engine), W9 (Organization governance via
approval_status), and the Memory Platform (checkpoint/resume)."""

from __future__ import annotations

import asyncio
import dataclasses

import pytest

from app import config, db
from app.consulting import tracking as ctracking
from app.consulting.engine import ConsultingEngine
from app.consulting.models import (
    EngagementCategory,
    EvidenceQuality,
    EvidenceSourceType,
)
from app.deliverables.errors import DeliverableError
from app.deliverables.generator import (
    export_validated_deliverable,
    generate_deliverable,
)
from app.deliverables.integration import (
    check_required_approvals,
    checkpoint_deliverable,
    resume_deliverable,
)
from app.deliverables.models import (
    Audience,
    DeliverableType,
    ExportFormat,
    VisualSpec,
    VisualType,
    new_visual_id,
)
from app.deliverables.registry import default_deliverable_registry
from app.synthesis import tracking as stracking
from app.synthesis.models import ApprovalStatus
from app.synthesis.state import SynthesisState


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _fresh_db(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "deliverables-test.db")
    db.reset_for_tests()
    yield


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


def test_check_required_approvals_reflects_real_w9_governed_approval_status():
    syn, ev = _synthesis_state()
    finding = stracking.create_finding(syn, "x", (ev.id,), 0.8, "y")
    rec = stracking.create_recommendation(syn, "s", "r", (finding.id,), (ev.id,))
    definition = default_deliverable_registry().get("business_case")

    satisfied, unsatisfied = check_required_approvals(definition, syn)
    assert not satisfied
    assert unsatisfied

    syn.recommendations[rec.id] = dataclasses.replace(
        rec, approval_status=ApprovalStatus.APPROVED
    )
    satisfied2, unsatisfied2 = check_required_approvals(definition, syn)
    assert satisfied2
    assert unsatisfied2 == ()


def test_checkpoint_and_resume_deliverable_round_trips_through_real_memory_platform():
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
    result = export_validated_deliverable(deliverable, syn, ExportFormat.MARKDOWN)

    checkpoint_result = _run(checkpoint_deliverable(deliverable, result))
    assert checkpoint_result.success

    resumed = _run(resume_deliverable(deliverable.id))
    assert resumed["id"] == deliverable.id
    assert resumed["quality_all_passed"] is True
    assert resumed["export_format"] == "markdown"


def test_resume_without_a_prior_checkpoint_raises():
    with pytest.raises(DeliverableError):
        _run(resume_deliverable("never-checkpointed"))
