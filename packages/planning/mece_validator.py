"""MECE issue-tree validator (ADR-004 §4, ADR-005 Issue Tree Generator contract).

Rules enforced:
  1. Non-empty tree.
  2. Every parent reference resolves to an existing node id.
  3. No circular parent references.
  4. Every leaf node has an assigned owner.
  5. Every node question ends with "?" (questions, not topic labels).
  6. No duplicate questions across nodes.
"""

from __future__ import annotations

from dataclasses import dataclass

from state.sections.planning import IssueNode


@dataclass(frozen=True)
class MeceViolation:
    """A single MECE rule violation."""

    rule: str
    detail: str
    node_id: str | None = None


@dataclass(frozen=True)
class MeceReport:
    """Result of a MECE validation pass."""

    valid: bool
    violations: tuple[MeceViolation, ...]


def validate_mece(nodes: list[IssueNode]) -> MeceReport:
    """Return a :class:`MeceReport` for the issue tree rooted at *nodes*.

    All rules are checked; the first cycle found short-circuits further cycle
    detection to avoid quadratic blowup on deep trees.
    """
    if not nodes:
        return MeceReport(
            valid=False,
            violations=(MeceViolation("NON_EMPTY", "Issue tree must not be empty"),),
        )

    violations: list[MeceViolation] = []
    node_ids: set[str] = {n.id for n in nodes}

    # Rule 1 — all parent refs resolve.
    for node in nodes:
        if node.parent is not None and node.parent not in node_ids:
            violations.append(
                MeceViolation(
                    "UNRESOLVED_PARENT",
                    (
                        f"Node {node.id!r} parent {node.parent!r}"
                        " does not match any node id"
                    ),
                    node.id,
                )
            )

    # Rule 2 — no circular parent references (only if parents resolved).
    if not violations:
        _check_cycles(nodes, violations)

    # Determine leaf nodes (no node claims them as parent).
    parent_ids: set[str] = {n.parent for n in nodes if n.parent is not None}
    leaves = [n for n in nodes if n.id not in parent_ids]

    # Rule 3 — every leaf has an owner.
    for leaf in leaves:
        if not leaf.owner:
            violations.append(
                MeceViolation(
                    "LEAF_NO_OWNER",
                    (
                        f"Leaf node {leaf.id!r} "
                        f"({leaf.question[:50]!r}) has no owner"
                    ),
                    leaf.id,
                )
            )

    # Rule 4 — every node is phrased as a question.
    for node in nodes:
        if not node.question.rstrip().endswith("?"):
            violations.append(
                MeceViolation(
                    "NOT_A_QUESTION",
                    (
                        f"Node {node.id!r} question is a topic label, not a"
                        f" question: {node.question[:60]!r}"
                    ),
                    node.id,
                )
            )

    # Rule 5 — no duplicate questions.
    seen: dict[str, str] = {}
    for node in nodes:
        normalised = node.question.strip().lower()
        if normalised in seen:
            violations.append(
                MeceViolation(
                    "DUPLICATE_QUESTION",
                    (
                        f"Node {node.id!r} duplicates the question"
                        f" of {seen[normalised]!r}"
                    ),
                    node.id,
                )
            )
        else:
            seen[normalised] = node.id

    return MeceReport(valid=not violations, violations=tuple(violations))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _check_cycles(
    nodes: list[IssueNode],
    violations: list[MeceViolation],
) -> None:
    """Append a CYCLE violation for the first cycle found (DFS, in-place)."""
    parent_map: dict[str, str | None] = {n.id: n.parent for n in nodes}

    def _has_cycle(nid: str, visited: frozenset[str]) -> bool:
        if nid in visited:
            return True
        parent = parent_map.get(nid)
        if parent is None:
            return False
        return _has_cycle(parent, visited | {nid})

    for node in nodes:
        if _has_cycle(node.id, frozenset()):
            violations.append(
                MeceViolation(
                    "CYCLE",
                    (
                        f"Circular parent reference detected involving"
                        f" node {node.id!r}"
                    ),
                    node.id,
                )
            )
            break  # one cycle report is sufficient
