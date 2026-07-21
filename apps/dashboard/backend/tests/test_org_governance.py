"""Tests for decision governance: authority, escalation, delegation."""

from __future__ import annotations

import pytest

from app.organization.errors import InsufficientAuthorityError
from app.organization.governance import DelegationLedger, can_approve, request_approval
from app.organization.models import DecisionType
from app.organization.registry import default_organization_registry


def test_can_approve_reflects_declared_authority():
    r = default_organization_registry()
    financial_analyst = r.get("financial_analyst")
    assert can_approve(financial_analyst, DecisionType.APPROVE_HYPOTHESES)
    assert not can_approve(financial_analyst, DecisionType.APPROVE_RECOMMENDATIONS)


def test_request_approval_no_escalation_when_role_already_holds_authority():
    r = default_organization_registry()
    outcome = request_approval(r, "project_leader", DecisionType.APPROVE_FINDINGS)
    assert not outcome.escalated
    assert outcome.approved_by_role_id == "project_leader"


def test_request_approval_escalates_up_the_real_reporting_chain():
    r = default_organization_registry()
    outcome = request_approval(
        r, "financial_analyst", DecisionType.APPROVE_RECOMMENDATIONS
    )
    assert outcome.escalated
    assert outcome.approved_by_role_id == "principal"
    assert outcome.escalation_chain[0] == "financial_analyst"
    assert outcome.escalation_chain[-1] == "principal"


def test_request_approval_reports_gap_when_no_one_in_chain_has_authority():
    """Every role's chain terminates at managing_partner, who holds
    executive-summary/recommendations/implementation-plan authority — so a
    genuine "nobody in the chain can approve" case requires a role whose
    entire chain (excluding itself) is checked; we simulate it by checking a
    decision type deliberately absent from the whole table isn't possible,
    so instead assert the well-formed non-gap case explicitly covers the
    mechanism, and separately test the gap path via a synthetic registry."""
    import dataclasses

    from app.organization.registry import OrganizationRegistry

    r = OrganizationRegistry()
    base = default_organization_registry().get("data_analyst")
    isolated = dataclasses.replace(
        base, id="isolated_role", reporting_line=None, decision_authority=()
    )
    r.register(isolated)
    outcome = request_approval(r, "isolated_role", DecisionType.APPROVE_RECOMMENDATIONS)
    assert outcome.approved_by_role_id is None
    assert outcome.escalated
    assert "no role" in outcome.reason


def test_delegation_allows_a_role_to_approve_without_escalating():
    r = default_organization_registry()
    ledger = DelegationLedger()
    ledger.delegate(
        r,
        "partner",
        "principal",
        DecisionType.APPROVE_RECOMMENDATIONS,
        reason="on leave",
    )
    outcome = request_approval(
        r, "principal", DecisionType.APPROVE_RECOMMENDATIONS, delegations=ledger
    )
    assert not outcome.escalated
    assert outcome.approved_by_role_id == "principal"
    assert outcome.reason == "approved via delegation"


def test_delegating_authority_you_do_not_hold_raises():
    r = default_organization_registry()
    ledger = DelegationLedger()
    with pytest.raises(InsufficientAuthorityError):
        ledger.delegate(
            r, "data_analyst", "business_analyst", DecisionType.APPROVE_RECOMMENDATIONS
        )


def test_delegations_to_lists_active_delegations_for_a_role():
    r = default_organization_registry()
    ledger = DelegationLedger()
    ledger.delegate(r, "partner", "principal", DecisionType.APPROVE_RECOMMENDATIONS)
    delegations = ledger.delegations_to("principal")
    assert len(delegations) == 1
    assert delegations[0].from_role_id == "partner"
