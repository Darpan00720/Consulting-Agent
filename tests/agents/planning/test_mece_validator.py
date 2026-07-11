"""Tests for the MECE issue-tree validator (packages/planning/mece_validator.py).

All tests are deterministic and filesystem-free.
"""

from __future__ import annotations

from planning import MeceReport, MeceViolation, validate_mece
from state.identifiers import IssueNodeId
from state.sections.planning import IssueNode

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _node(
    question: str,
    owner: str | None = "financial-analyst",
    parent: str | None = None,
    nid: str | None = None,
) -> IssueNode:
    """Build a minimal IssueNode (id auto-generated unless nid supplied)."""
    kwargs: dict[str, object] = {"question": question, "owner": owner}
    if parent is not None:
        kwargs["parent"] = parent
    node = IssueNode(**kwargs)  # type: ignore[arg-type]
    if nid is not None:
        # Override the auto-generated id via model_copy
        node = node.model_copy(update={"id": IssueNodeId(nid)})
    return node


def _valid_tree() -> list[IssueNode]:
    """Minimal valid 3-node tree: root → two leaves."""
    root = _node("Is the margin declining?", owner=None, nid="root")
    left = _node(
        "Is the margin decline driven by price?",
        owner="financial-analyst",
        parent="root",
    )
    right = _node(
        "Is the margin decline driven by volume?",
        owner="financial-analyst",
        parent="root",
    )
    return [root, left, right]


# ---------------------------------------------------------------------------
# Empty tree
# ---------------------------------------------------------------------------


def test_empty_tree_is_invalid() -> None:
    report = validate_mece([])
    assert not report.valid
    assert any(v.rule == "NON_EMPTY" for v in report.violations)


# ---------------------------------------------------------------------------
# Valid trees
# ---------------------------------------------------------------------------


def test_valid_tree_passes() -> None:
    report = validate_mece(_valid_tree())
    assert report.valid, report.violations


def test_single_leaf_root_passes() -> None:
    node = _node("Is the business profitable?", owner="financial-analyst")
    report = validate_mece([node])
    assert report.valid, report.violations


# ---------------------------------------------------------------------------
# Unresolved parent reference
# ---------------------------------------------------------------------------


def test_unresolved_parent_fails() -> None:
    node = _node("Is revenue declining?", owner="market-analyst", parent="nonexistent")
    report = validate_mece([node])
    assert not report.valid
    assert any(v.rule == "UNRESOLVED_PARENT" for v in report.violations)


# ---------------------------------------------------------------------------
# Circular reference
# ---------------------------------------------------------------------------


def test_cycle_fails() -> None:
    a = _node("Is price declining?", owner="financial-analyst", nid="a")
    b = _node("Is volume declining?", owner="financial-analyst", nid="b", parent="a")
    a = a.model_copy(update={"parent": "b"})  # a → b and b → a
    report = validate_mece([a, b])
    assert not report.valid
    assert any(v.rule == "CYCLE" for v in report.violations)


# ---------------------------------------------------------------------------
# Leaf without owner
# ---------------------------------------------------------------------------


def test_leaf_without_owner_fails() -> None:
    root = _node("Is profitability declining?", owner=None, nid="root")
    leaf = _node(
        "Is gross margin declining?",
        owner=None,  # missing owner
        parent="root",
    )
    report = validate_mece([root, leaf])
    assert not report.valid
    assert any(v.rule == "LEAF_NO_OWNER" for v in report.violations)


def test_parent_node_may_have_no_owner() -> None:
    """A parent node with owner=None is valid; only leaves must have owners."""
    root = _node("Is profitability declining?", owner=None, nid="root")
    l1 = _node(
        "Is revenue declining?",
        owner=None,
        parent="root",
        nid="l1",
    )
    leaf_a = _node("Is price declining?", owner="financial-analyst", parent="l1")
    leaf_b = _node("Is volume declining?", owner="financial-analyst", parent="l1")
    report = validate_mece([root, l1, leaf_a, leaf_b])
    assert report.valid, report.violations


# ---------------------------------------------------------------------------
# Questions vs. topic labels
# ---------------------------------------------------------------------------


def test_topic_label_fails() -> None:
    node = _node("Pricing Analysis", owner="financial-analyst")  # no "?"
    report = validate_mece([node])
    assert not report.valid
    assert any(v.rule == "NOT_A_QUESTION" for v in report.violations)


def test_question_with_trailing_whitespace_passes() -> None:
    node = _node("Is pricing the issue? ", owner="financial-analyst")
    report = validate_mece([node])
    # NOT_A_QUESTION should not fire for trailing space after "?"
    assert not any(v.rule == "NOT_A_QUESTION" for v in report.violations)


# ---------------------------------------------------------------------------
# Duplicate questions
# ---------------------------------------------------------------------------


def test_duplicate_question_fails() -> None:
    a = _node("Is revenue declining?", owner="financial-analyst")
    b = _node("Is revenue declining?", owner="market-analyst")
    report = validate_mece([a, b])
    assert not report.valid
    assert any(v.rule == "DUPLICATE_QUESTION" for v in report.violations)


def test_case_insensitive_duplicate_fails() -> None:
    a = _node("Is revenue declining?", owner="financial-analyst")
    b = _node("IS REVENUE DECLINING?", owner="market-analyst")
    report = validate_mece([a, b])
    assert not report.valid
    assert any(v.rule == "DUPLICATE_QUESTION" for v in report.violations)


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


def test_return_type_is_mece_report() -> None:
    report = validate_mece(_valid_tree())
    assert isinstance(report, MeceReport)
    assert isinstance(report.violations, tuple)


def test_violations_are_mece_violation_instances() -> None:
    node = _node("Topic label", owner=None)
    report = validate_mece([node])
    for v in report.violations:
        assert isinstance(v, MeceViolation)
        assert isinstance(v.rule, str)
        assert isinstance(v.detail, str)


# ---------------------------------------------------------------------------
# Multiple violations accumulate
# ---------------------------------------------------------------------------


def test_multiple_violations_all_reported() -> None:
    # Topic label + no owner — should report both violations
    node = _node("Pricing", owner=None)
    report = validate_mece([node])
    rules = {v.rule for v in report.violations}
    assert "NOT_A_QUESTION" in rules
    assert "LEAF_NO_OWNER" in rules


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_same_input_produces_same_output() -> None:
    tree = _valid_tree()
    r1 = validate_mece(tree)
    r2 = validate_mece(tree)
    assert r1.valid == r2.valid
    assert r1.violations == r2.violations
