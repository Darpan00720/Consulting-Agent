"""Tests for the multi-stage review workflow."""

from __future__ import annotations

from app.organization.models import ReviewChecklistInput, ReviewOutcome, ReviewStage
from app.organization.registry import default_organization_registry
from app.organization.review import ReviewHistory, submit_for_review


def test_full_checklist_passes_is_approved():
    r = default_organization_registry()
    qa = r.get("qa_reviewer")
    result = submit_for_review("art-1", ReviewStage.MANAGER, qa, ReviewChecklistInput())
    assert result.outcome is ReviewOutcome.APPROVED
    assert len(result.checklist) == 7


def test_substantive_failure_requires_rework():
    r = default_organization_registry()
    qa = r.get("qa_reviewer")
    result = submit_for_review(
        "art-1", ReviewStage.MANAGER, qa, ReviewChecklistInput(evidence_traceable=False)
    )
    assert result.outcome is ReviewOutcome.REWORK_REQUIRED


def test_clarity_only_failure_is_approved_with_comments():
    r = default_organization_registry()
    qa = r.get("qa_reviewer")
    result = submit_for_review(
        "art-1",
        ReviewStage.MANAGER,
        qa,
        ReviewChecklistInput(clarity=False, comments=("tighten the summary",)),
    )
    assert result.outcome is ReviewOutcome.APPROVED_WITH_COMMENTS
    assert result.comments == ("tighten the summary",)


def test_reviewer_without_stage_authority_is_rejected():
    r = default_organization_registry()
    analyst = r.get("data_analyst")  # PEER-only review authority
    result = submit_for_review(
        "art-1", ReviewStage.EXECUTIVE, analyst, ReviewChecklistInput()
    )
    assert result.outcome.value == "rejected"
    assert "does not hold" in result.comments[0]


def test_partner_can_conduct_partner_stage_review():
    r = default_organization_registry()
    partner = r.get("partner")
    result = submit_for_review(
        "art-1", ReviewStage.PARTNER, partner, ReviewChecklistInput()
    )
    assert result.outcome is ReviewOutcome.APPROVED


def test_managing_partner_can_conduct_executive_review():
    r = default_organization_registry()
    mp = r.get("managing_partner")
    result = submit_for_review(
        "art-1", ReviewStage.EXECUTIVE, mp, ReviewChecklistInput()
    )
    assert result.outcome is ReviewOutcome.APPROVED


def test_review_history_tracks_iterations_until_approved():
    r = default_organization_registry()
    qa = r.get("qa_reviewer")
    history = ReviewHistory()

    r1 = submit_for_review(
        "art-1", ReviewStage.MANAGER, qa, ReviewChecklistInput(logic_sound=False)
    )
    history.record(r1)
    assert history.iteration_count("art-1") == 1
    assert not history.is_approved("art-1")

    r2 = submit_for_review("art-1", ReviewStage.MANAGER, qa, ReviewChecklistInput())
    history.record(r2)
    assert history.iteration_count("art-1") == 2
    assert history.is_approved("art-1")


def test_history_for_unknown_artifact_is_empty():
    history = ReviewHistory()
    assert history.history_for("never-reviewed") == ()
    assert history.iteration_count("never-reviewed") == 0
    assert not history.is_approved("never-reviewed")
