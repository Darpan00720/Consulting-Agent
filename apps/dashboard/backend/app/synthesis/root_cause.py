"""Root cause analysis engine (requester's "Root Cause Analysis" section):
reusable structuring support for 5 Whys, Fishbone/Ishikawa, Fault Tree, and
Cause Mapping. Multiple root causes are supported by every method.

**Structures caller-supplied cause chains; never discovers causes itself**
— identifying WHY something happened is analyst judgment, the same
"generic scaffolding over caller-supplied content" split every reasoning
tool in this package makes (mirrors ``app.knowledge.execution``'s framework
boundary one layer up).
"""

from __future__ import annotations

from app.synthesis.errors import SynthesisError
from app.synthesis.models import RootCauseAnalysis, RootCauseMethod, RootCauseNode


def _new_node_id(prefix: str, index: int) -> str:
    return f"{prefix}-{index}"


def _validate(
    nodes: tuple[RootCauseNode, ...], root_cause_ids: tuple[str, ...]
) -> None:
    ids = {n.id for n in nodes}
    if len(ids) != len(nodes):
        raise SynthesisError("duplicate node ids in root cause analysis")
    for node in nodes:
        if node.parent_id is not None and node.parent_id not in ids:
            raise SynthesisError(
                f"node {node.id!r} references missing parent {node.parent_id!r}"
            )
    missing_roots = set(root_cause_ids) - ids
    if missing_roots:
        raise SynthesisError(
            f"root_cause_ids reference missing nodes: {sorted(missing_roots)}"
        )


def build_root_cause_analysis(
    method: RootCauseMethod,
    problem_statement: str,
    nodes: tuple[RootCauseNode, ...],
    root_cause_ids: tuple[str, ...],
) -> RootCauseAnalysis:
    """The generic builder every convenience constructor below reduces to.
    Supports multiple root causes: ``root_cause_ids`` is a tuple, not a
    single id."""
    _validate(nodes, root_cause_ids)
    from app.synthesis.models import new_root_cause_analysis_id

    return RootCauseAnalysis(
        id=new_root_cause_analysis_id(),
        method=method,
        problem_statement=problem_statement,
        nodes=nodes,
        root_cause_ids=root_cause_ids,
    )


def five_whys(
    problem_statement: str, why_chains: tuple[tuple[str, ...], ...]
) -> RootCauseAnalysis:
    """Each entry in ``why_chains`` is one independent chain of "why"
    statements (why[0] caused by why[1], caused by why[2], ...); the LAST
    statement in each chain is a root cause. Multiple chains -> multiple
    root causes."""
    nodes: list[RootCauseNode] = []
    root_cause_ids: list[str] = []
    for chain_index, chain in enumerate(why_chains):
        parent_id: str | None = None
        node_id = ""
        for depth, statement in enumerate(chain):
            node_id = _new_node_id(f"chain{chain_index}", depth)
            nodes.append(
                RootCauseNode(id=node_id, statement=statement, parent_id=parent_id)
            )
            parent_id = node_id
        if chain:
            root_cause_ids.append(node_id)
    return build_root_cause_analysis(
        RootCauseMethod.FIVE_WHYS,
        problem_statement,
        tuple(nodes),
        tuple(root_cause_ids),
    )


def fishbone(
    problem_statement: str,
    categories: dict,
) -> RootCauseAnalysis:
    """``categories`` maps a category name (e.g. "people", "process",
    "technology", "environment") to a tuple of specific causes under it.
    Every leaf cause is a root cause — a fishbone diagram is explicitly
    meant to surface multiple parallel root causes across categories."""
    nodes: list[RootCauseNode] = []
    root_cause_ids: list[str] = []
    for cat_index, (category, causes) in enumerate(categories.items()):
        cat_node_id = _new_node_id("cat", cat_index)
        nodes.append(
            RootCauseNode(
                id=cat_node_id, statement=category, parent_id=None, category=category
            )
        )
        for cause_index, cause in enumerate(causes):
            cause_id = f"{cat_node_id}-cause{cause_index}"
            nodes.append(
                RootCauseNode(
                    id=cause_id,
                    statement=cause,
                    parent_id=cat_node_id,
                    category=category,
                )
            )
            root_cause_ids.append(cause_id)
    return build_root_cause_analysis(
        RootCauseMethod.FISHBONE, problem_statement, tuple(nodes), tuple(root_cause_ids)
    )


def fault_tree(
    problem_statement: str,
    top_event: str,
    intermediate_events: dict,
) -> RootCauseAnalysis:
    """``intermediate_events`` maps an intermediate-event statement to a
    tuple of basic events (leaf causes) beneath it. The top event is the
    tree's root node; every basic event is a potential root cause."""
    nodes: list[RootCauseNode] = [
        RootCauseNode(id="top", statement=top_event, parent_id=None)
    ]
    root_cause_ids: list[str] = []
    for event_index, (intermediate, basic_events) in enumerate(
        intermediate_events.items()
    ):
        inter_id = _new_node_id("intermediate", event_index)
        nodes.append(
            RootCauseNode(id=inter_id, statement=intermediate, parent_id="top")
        )
        for basic_index, basic in enumerate(basic_events):
            basic_id = f"{inter_id}-basic{basic_index}"
            nodes.append(
                RootCauseNode(id=basic_id, statement=basic, parent_id=inter_id)
            )
            root_cause_ids.append(basic_id)
    return build_root_cause_analysis(
        RootCauseMethod.FAULT_TREE,
        problem_statement,
        tuple(nodes),
        tuple(root_cause_ids),
    )


def cause_mapping(
    problem_statement: str,
    cause_edges: tuple[tuple[str, str], ...],
) -> RootCauseAnalysis:
    """Each edge is ``(effect_statement, cause_statement)`` — a general
    cause-and-effect DAG where multiple causes can converge on one effect.
    Root causes are statements that never appear as an effect anywhere in
    the map (nothing points further back from them)."""
    statement_to_id: dict[str, str] = {}
    nodes: list[RootCauseNode] = []

    def _node_for(statement: str) -> str:
        if statement not in statement_to_id:
            node_id = f"node{len(statement_to_id)}"
            statement_to_id[statement] = node_id
        return statement_to_id[statement]

    parent_of: dict[str, str | None] = {}
    for effect, cause in cause_edges:
        effect_id = _node_for(effect)
        cause_id = _node_for(cause)
        parent_of[cause_id] = effect_id
        parent_of.setdefault(effect_id, None)

    for statement, node_id in statement_to_id.items():
        nodes.append(
            RootCauseNode(
                id=node_id, statement=statement, parent_id=parent_of.get(node_id)
            )
        )

    effects = {effect for effect, _cause in cause_edges}
    root_cause_ids = tuple(
        statement_to_id[s] for s in statement_to_id if s not in effects
    )
    return build_root_cause_analysis(
        RootCauseMethod.CAUSE_MAPPING, problem_statement, tuple(nodes), root_cause_ids
    )
