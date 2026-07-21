"""Decision governance (requester's "Decision Governance" section): which
roles may approve hypotheses/assumptions/findings/recommendations/
implementation plans/executive summaries, with delegation and escalation.

Escalation walks the REAL reporting chain (``OrganizationRegistry.
reporting_chain``) — never a separately hardcoded escalation table that
could drift from who actually reports to whom.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.organization.errors import InsufficientAuthorityError
from app.organization.models import (
    ApprovalOutcome,
    DecisionType,
    DelegationRecord,
    RoleDefinition,
)
from app.organization.registry import OrganizationRegistry


def can_approve(role: RoleDefinition, decision: DecisionType) -> bool:
    return decision in role.decision_authority


@dataclass
class DelegationLedger:
    """Active delegations — a role that itself holds authority for a
    decision can delegate it to a specific other role. Delegating authority
    you do not hold is a genuine invariant violation, not an expected
    outcome, so it raises (the same "raise only for a domain rule"
    exception this platform's error hierarchies already carve out)."""

    _delegations: list[DelegationRecord] = field(default_factory=list)

    def delegate(
        self,
        registry: OrganizationRegistry,
        from_role_id: str,
        to_role_id: str,
        decision: DecisionType,
        reason: str = "",
    ) -> DelegationRecord:
        from_role = registry.get(from_role_id)
        registry.get(
            to_role_id
        )  # raises UnknownRoleError if the delegate doesn't exist
        if not can_approve(from_role, decision):
            raise InsufficientAuthorityError(
                f"{from_role_id!r} cannot delegate {decision.value!r}: it does "
                "not hold that authority itself"
            )
        record = DelegationRecord(
            decision=decision,
            from_role_id=from_role_id,
            to_role_id=to_role_id,
            reason=reason,
        )
        self._delegations.append(record)
        return record

    def has_delegation(self, to_role_id: str, decision: DecisionType) -> bool:
        return any(
            d.to_role_id == to_role_id and d.decision is decision
            for d in self._delegations
        )

    def delegations_to(self, to_role_id: str) -> tuple[DelegationRecord, ...]:
        return tuple(d for d in self._delegations if d.to_role_id == to_role_id)


def request_approval(
    registry: OrganizationRegistry,
    requesting_role_id: str,
    decision: DecisionType,
    *,
    delegations: DelegationLedger | None = None,
) -> ApprovalOutcome:
    """Never raises: the terminal case (no role in the reporting chain holds
    this authority) is a reportable organizational gap, not an exception —
    the same discipline every dispatch/execution layer in this platform
    already follows for its own "never raise" boundary."""
    if delegations is not None and delegations.has_delegation(
        requesting_role_id, decision
    ):
        return ApprovalOutcome(
            decision=decision,
            requested_by_role_id=requesting_role_id,
            approved_by_role_id=requesting_role_id,
            escalated=False,
            escalation_chain=(requesting_role_id,),
            reason="approved via delegation",
        )

    chain = registry.reporting_chain(requesting_role_id)
    for i, role in enumerate(chain):
        if can_approve(role, decision):
            return ApprovalOutcome(
                decision=decision,
                requested_by_role_id=requesting_role_id,
                approved_by_role_id=role.id,
                escalated=i > 0,
                escalation_chain=tuple(r.id for r in chain[: i + 1]),
            )

    return ApprovalOutcome(
        decision=decision,
        requested_by_role_id=requesting_role_id,
        approved_by_role_id=None,
        escalated=True,
        escalation_chain=tuple(r.id for r in chain),
        reason=f"no role in {requesting_role_id!r}'s reporting chain holds "
        f"{decision.value!r} authority",
    )
