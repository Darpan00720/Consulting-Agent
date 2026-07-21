"""Tests for the executive communication (audience) model — emphasis
adjusts presentation only, never underlying content."""

from __future__ import annotations

from app.deliverables.audience import order_sections_for_audience, profile_for
from app.deliverables.models import Audience


def test_every_audience_has_a_profile():
    for audience in Audience:
        profile = profile_for(audience)
        assert profile.audience is audience
        assert profile.emphasis_sections
        assert profile.framing_notes


def test_order_sections_moves_emphasized_sections_to_front():
    sections = (
        "appendix_evidence",
        "business_case",
        "executive_summary",
        "key_findings",
    )
    ordered = order_sections_for_audience(Audience.CFO, sections)
    assert ordered[0] == "business_case"  # CFO emphasizes business_case first


def test_order_sections_never_adds_or_removes_sections():
    sections = ("cover", "key_findings", "recommendations")
    ordered = order_sections_for_audience(Audience.CEO, sections)
    assert set(ordered) == set(sections)
    assert len(ordered) == len(sections)


def test_order_sections_is_a_no_op_when_nothing_matches():
    sections = ("appendix_evidence",)
    ordered = order_sections_for_audience(Audience.CEO, sections)
    assert ordered == sections
