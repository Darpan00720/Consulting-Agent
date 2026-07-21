"""Tests for ``EngagementState`` supporting structures, especially the
structural MECE validator (``validate_mece``) — the "detect overlaps, detect
gaps" requirement for the Issue Tree stage."""

from __future__ import annotations

from app.consulting.state import IssueNode, IssueTree, validate_mece


def _tree(nodes: dict[str, IssueNode], root_id: str = "root") -> IssueTree:
    return IssueTree(root_id=root_id, nodes=nodes)


def test_valid_mece_tree_passes():
    tree = _tree(
        {
            "root": IssueNode(
                id="root", question="How to grow revenue?", parent_id=None
            ),
            "n1": IssueNode(
                id="n1", question="Expand into new markets?", parent_id="root"
            ),
            "n2": IssueNode(
                id="n2",
                question="Increase share in existing markets?",
                parent_id="root",
            ),
        }
    )
    ok, issues = validate_mece(tree)
    assert ok, issues
    assert issues == ()


def test_missing_root_id_fails():
    tree = _tree(
        {"n1": IssueNode(id="n1", question="Q", parent_id=None)}, root_id="root"
    )
    ok, issues = validate_mece(tree)
    assert not ok
    assert "root_id not present" in issues[0]


def test_multiple_roots_detected():
    tree = _tree(
        {
            "root": IssueNode(id="root", question="Q1", parent_id=None),
            "other_root": IssueNode(id="other_root", question="Q2", parent_id=None),
        }
    )
    ok, issues = validate_mece(tree)
    assert not ok
    assert any("exactly one root" in i for i in issues)


def test_missing_parent_reference_detected():
    tree = _tree(
        {
            "root": IssueNode(id="root", question="Q", parent_id=None),
            "orphan": IssueNode(id="orphan", question="Q2", parent_id="ghost"),
        }
    )
    ok, issues = validate_mece(tree)
    assert not ok
    assert any("missing parent" in i for i in issues)


def test_cycle_detected():
    tree = _tree(
        {
            "root": IssueNode(id="root", question="Q", parent_id=None),
            "a": IssueNode(id="a", question="A", parent_id="b"),
            "b": IssueNode(id="b", question="B", parent_id="a"),
        }
    )
    ok, issues = validate_mece(tree)
    assert not ok
    assert any("cycle" in i for i in issues)


def test_duplicate_sibling_questions_detected_as_mutual_exclusivity_break():
    tree = _tree(
        {
            "root": IssueNode(id="root", question="Q", parent_id=None),
            "n1": IssueNode(id="n1", question="Same question?", parent_id="root"),
            "n2": IssueNode(id="n2", question="same question?", parent_id="root"),
        }
    )
    ok, issues = validate_mece(tree)
    assert not ok
    assert any("duplicate sibling questions" in i for i in issues)
