"""Tests for the declarative Permission Policy (ADR-013 W5, requirement 5).

Specificity ordering, override behavior, and the fail-closed default (no
matching rule => DENY, never ALLOW).
"""

from __future__ import annotations

from app.tools.models import OperationClass, PermissionDecision
from app.tools.permissions import DEFAULT_RULES, PermissionPolicy, PermissionRule

_RO = OperationClass.READ_ONLY
_WR = OperationClass.WRITE
_DG = OperationClass.DANGEROUS
_OFF = OperationClass.OFFLINE

_ALLOW = PermissionDecision.ALLOW
_DENY = PermissionDecision.DENY
_INTERACTIVE = PermissionDecision.INTERACTIVE


def test_default_rules_allow_read_only():
    policy = PermissionPolicy()
    assert policy.evaluate("any-tool", _RO) is _ALLOW


def test_default_rules_allow_offline():
    policy = PermissionPolicy()
    assert policy.evaluate("any-tool", _OFF) is _ALLOW


def test_default_rules_require_interactive_for_write():
    policy = PermissionPolicy()
    assert policy.evaluate("any-tool", _WR) is _INTERACTIVE


def test_default_rules_deny_dangerous():
    policy = PermissionPolicy()
    assert policy.evaluate("any-tool", _DG) is _DENY


def test_no_matching_rule_fails_closed_to_deny():
    """An empty policy (no rules at all) must DENY, never silently allow —
    the one place this platform fails CLOSED rather than open."""
    policy = PermissionPolicy(rules=())
    assert policy.evaluate("any-tool", _RO) is _DENY


def test_exact_tool_rule_overrides_wildcard():
    policy = PermissionPolicy()
    policy.deny("local-shell", _RO)  # more specific than the wildcard ALLOW
    assert policy.evaluate("local-shell", _RO) is _DENY
    assert policy.evaluate("other-tool", _RO) is _ALLOW  # unaffected


def test_exact_tool_any_class_beats_wildcard_exact_class():
    """('tool', None) is more specific than ('*', exact-class) — a per-tool
    blanket rule wins over a global per-class default."""
    policy = PermissionPolicy(rules=[PermissionRule("*", _DG, _DENY)])
    policy.allow("special-tool", None)  # blanket allow for this one tool
    assert policy.evaluate("special-tool", _DG) is _ALLOW
    assert policy.evaluate("other-tool", _DG) is _DENY


def test_later_rule_wins_among_equal_specificity():
    policy = PermissionPolicy(rules=[])
    policy.add_rule(PermissionRule("a", _RO, _ALLOW))
    policy.add_rule(PermissionRule("a", _RO, _DENY))  # same specificity, added later
    assert policy.evaluate("a", _RO) is _DENY


def test_allow_convenience_method():
    policy = PermissionPolicy(rules=[])
    policy.allow("local-shell", _DG)
    assert policy.evaluate("local-shell", _DG) is _ALLOW


def test_require_approval_convenience_method():
    policy = PermissionPolicy(rules=[])
    policy.require_approval("github", _WR)
    assert policy.evaluate("github", _WR) is _INTERACTIVE


def test_local_shell_dangerous_denied_even_with_allowlisted_command():
    """Two independent gates (allow-list at the adapter, policy at the
    Runtime) must both open — this test proves the POLICY gate alone still
    denies, regardless of what the adapter's own allow-list contains."""
    policy = PermissionPolicy()  # defaults: DANGEROUS -> DENY
    assert policy.evaluate("local-shell", _DG) is _DENY


def test_default_rules_constant_has_all_four_classes_covered():
    covered = {rule.operation_class for rule in DEFAULT_RULES}
    assert covered == {_RO, _WR, _DG, _OFF}
