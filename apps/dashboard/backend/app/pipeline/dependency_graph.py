"""Dependency Graph (ADR-010 Phase 3).

A real graph — adjacency list, DFS cycle detection, Kahn topological sort —
over LLM-declared :class:`~app.pipeline.consulting_schema.DependencyEdge`
objects (technology/budget/people/regulatory/data/vendor/change-management/
timeline dependencies a recommendation has on something else). The LLM
declares WHICH things depend on which; the graph algorithms — genuinely
deterministic, no judgment involved — answer "is this even executable" (no
cycle) and "in what order" (topological sort), for Governance (P4) to query.

Same algorithm shape as ``quantcheck``'s formula-dependency cycle check
(ADR-009) and ``ledger_builder``'s topological evaluation order (ADR-010 P1)
— this module is that same, well-tested pattern applied to consulting
dependencies instead of ledger formulas.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.pipeline.consulting_schema import DependencyEdge


class DependencyGraphError(ValueError):
    """A structural problem in the graph itself (unknown node in an edge)."""


@dataclass(frozen=True)
class CycleReport:
    has_cycle: bool
    cycle: tuple[str, ...] = ()  # the cycle's node ids, in order, if found


class DependencyGraph:
    """Directed graph: an edge ``from_id -> to_id`` means "``from_id``
    depends on ``to_id``" (``to_id`` must happen/exist first)."""

    def __init__(self, edges: list[DependencyEdge]) -> None:
        self._edges = list(edges)
        self._adj: dict[str, list[str]] = {}
        self._nodes: set[str] = set()
        for edge in edges:
            self._nodes.add(edge.from_id)
            self._nodes.add(edge.to_id)
            self._adj.setdefault(edge.from_id, []).append(edge.to_id)

    def nodes(self) -> tuple[str, ...]:
        return tuple(sorted(self._nodes))

    def depends_on(self, node_id: str) -> tuple[str, ...]:
        return tuple(self._adj.get(node_id, ()))

    def blocked_by(self, node_id: str) -> tuple[str, ...]:
        """Every node ``node_id`` (directly or transitively) depends on —
        "what has to happen before this recommendation can execute"."""
        seen: set[str] = set()
        stack = list(self._adj.get(node_id, ()))
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            stack.extend(self._adj.get(current, ()))
        return tuple(sorted(seen))

    def detect_cycle(self) -> CycleReport:
        """DFS cycle detection — the same WHITE/GREY/BLACK algorithm shape
        ``quantcheck._cycles`` and ``ledger_builder._topo_order`` already use
        for the ledger's formula dependency graph."""
        WHITE, GREY, BLACK = 0, 1, 2
        color = dict.fromkeys(self._nodes, WHITE)

        def visit(node: str, path: list[str]) -> tuple[str, ...] | None:
            color[node] = GREY
            path.append(node)
            for dep in self._adj.get(node, ()):
                if color[dep] == GREY:
                    return tuple(path[path.index(dep) :] + [dep])
                if color[dep] == WHITE:
                    found = visit(dep, path)
                    if found:
                        return found
            path.pop()
            color[node] = BLACK
            return None

        for node in sorted(self._nodes):
            if color[node] == WHITE:
                cycle = visit(node, [])
                if cycle:
                    return CycleReport(True, cycle)
        return CycleReport(False)

    def topological_order(self) -> tuple[str, ...]:
        """Kahn's algorithm: an execution order where every node appears
        after everything it depends on. Raises if the graph has a cycle —
        there is no valid order to return, and silently returning a wrong one
        would be worse than refusing (same fail-closed discipline as every
        other gate in this pipeline)."""
        cycle = self.detect_cycle()
        if cycle.has_cycle:
            raise DependencyGraphError(
                "cannot topologically order a cyclic graph: " + " -> ".join(cycle.cycle)
            )

        # Our edges point dependent -> prerequisite ("from_id depends on
        # to_id"), the opposite of Kahn's classic prerequisite -> dependent
        # direction — so we process nodes with zero OUTSTANDING dependencies
        # first, and walk the REVERSE adjacency to decrement each dependent's
        # count as its prerequisites clear.
        reverse_adj: dict[str, list[str]] = {n: [] for n in self._nodes}
        for from_id, deps in self._adj.items():
            for to_id in deps:
                reverse_adj[to_id].append(from_id)
        remaining_deps = {n: len(self._adj.get(n, [])) for n in self._nodes}
        ready = sorted(n for n, d in remaining_deps.items() if d == 0)
        order: list[str] = []
        while ready:
            node = ready.pop(0)
            order.append(node)
            for dependent in sorted(reverse_adj[node]):
                remaining_deps[dependent] -= 1
                if remaining_deps[dependent] == 0:
                    ready.append(dependent)
            ready.sort()
        if len(order) != len(self._nodes):
            # Should be unreachable given the cycle check above; fail loud if
            # it ever happens rather than return a silently incomplete order.
            raise DependencyGraphError(
                "topological sort did not cover every node — internal "
                "inconsistency between cycle detection and ordering."
            )
        return tuple(order)


def build_graph(edges: list[DependencyEdge]) -> DependencyGraph:
    return DependencyGraph(edges)
