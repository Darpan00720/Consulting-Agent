"""Permission policy (requirement 5) — declarative allow/deny/interactive
rules over (tool, operation-class) pairs.

Rules are DATA (``PermissionRule`` tuples), evaluated by ``PermissionPolicy``
— no code branch per tool, so a new tool never requires a policy-engine
change (requirement 9: plugin-friendly). Fail-closed: a request matching no
rule is DENIED, never silently allowed.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.tools.models import OperationClass, PermissionDecision

WILDCARD = "*"


@dataclass(frozen=True)
class PermissionRule:
    """One declarative rule. ``tool_id="*"`` matches any tool;
    ``operation_class=None`` matches any class."""

    tool_id: str
    operation_class: OperationClass | None
    decision: PermissionDecision


# Conservative-by-default rule set (requirement 5's four decision-relevant
# classes): offline/read-only operations proceed automatically; writes need a
# human in the loop; anything DANGEROUS is denied until a caller explicitly
# opts a specific tool in.
DEFAULT_RULES: tuple[PermissionRule, ...] = (
    PermissionRule(WILDCARD, OperationClass.OFFLINE, PermissionDecision.ALLOW),
    PermissionRule(WILDCARD, OperationClass.READ_ONLY, PermissionDecision.ALLOW),
    PermissionRule(WILDCARD, OperationClass.WRITE, PermissionDecision.INTERACTIVE),
    PermissionRule(WILDCARD, OperationClass.DANGEROUS, PermissionDecision.DENY),
)


class PermissionPolicy:
    """Evaluates a (tool_id, operation_class) pair against declarative rules.

    Specificity order (most specific wins): exact tool + exact class >
    exact tool + any class > wildcard + exact class > wildcard + any class.
    Among equally-specific matches, the MOST RECENTLY ADDED rule wins — so a
    caller can override a default by appending a more targeted or later rule.
    No matching rule at all → DENY (fail-closed, never fail-open on
    permissions — the opposite discipline from every other layer's
    fail-open-to-safe-default, deliberately, because "silently allow an
    unclassified dangerous operation" is the one failure mode this platform
    must never produce).
    """

    def __init__(self, rules: Sequence[PermissionRule] | None = None) -> None:
        self.rules: list[PermissionRule] = (
            list(rules) if rules is not None else list(DEFAULT_RULES)
        )

    def add_rule(self, rule: PermissionRule) -> None:
        self.rules.append(rule)

    def allow(
        self, tool_id: str, operation_class: OperationClass | None = None
    ) -> None:
        self.add_rule(
            PermissionRule(tool_id, operation_class, PermissionDecision.ALLOW)
        )

    def deny(self, tool_id: str, operation_class: OperationClass | None = None) -> None:
        self.add_rule(PermissionRule(tool_id, operation_class, PermissionDecision.DENY))

    def require_approval(
        self, tool_id: str, operation_class: OperationClass | None = None
    ) -> None:
        self.add_rule(
            PermissionRule(tool_id, operation_class, PermissionDecision.INTERACTIVE)
        )

    def evaluate(
        self, tool_id: str, operation_class: OperationClass
    ) -> PermissionDecision:
        best_score = -1
        best_decision: PermissionDecision | None = None
        for rule in self.rules:
            tool_match = rule.tool_id in (tool_id, WILDCARD)
            class_match = (
                rule.operation_class is None or rule.operation_class == operation_class
            )
            if not (tool_match and class_match):
                continue
            score = (2 if rule.tool_id == tool_id else 0) + (
                1 if rule.operation_class is not None else 0
            )
            if score >= best_score:  # >= so the LATEST equally-specific rule wins
                best_score = score
                best_decision = rule.decision
        return best_decision if best_decision is not None else PermissionDecision.DENY
