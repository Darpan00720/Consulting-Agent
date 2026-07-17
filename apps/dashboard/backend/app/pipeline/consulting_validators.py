"""Consulting Intelligence Layer — deterministic validators (ADR-010 Phase 3).

Every function here CHECKS a consulting artifact against
``consulting_schema.py``'s contracts; none of them GENERATE one (ADR-010 §6b:
generation is judgment, judgment is the LLM's job). This is the same
division P1 draws for arithmetic and P2 draws for evidence: an LLM proposes,
code verifies completeness/consistency.
"""

from __future__ import annotations

from dataclasses import replace

from app.pipeline.consulting_schema import (
    CapabilityFlag,
    Hypothesis,
    IssueTree,
    ResearchPlan,
    StrategicOption,
)
from app.pipeline.evidence_store import EvidenceStore

# --- MECE / issue-tree structural completeness ------------------------------------


def check_mece_completeness(tree: IssueTree) -> list[str]:
    """Structural checks only (ADR-010 §6b: true semantic MECE-ness — are two
    differently-worded branches ACTUALLY mutually exclusive in meaning — is
    not something code can verify; that stays a human/reviewer judgment).

    Checked:
    - every ``parent_id`` resolves to a real node (no dangling tree edges);
    - no two LEAF nodes share a ``scope_tag`` (the deterministic proxy for
      Mutual Exclusivity — the actual partition the tree claims to make);
    - every leaf has at least one owner (schema already enforces this) and at
      least one hypothesis reference (Collectively Exhaustive requires every
      leaf to be traceable to a testable claim, not left as decoration).
    """
    defects: list[str] = []
    ids = {n.node_id for n in tree.nodes}
    for node in tree.nodes:
        if node.parent_id is not None and node.parent_id not in ids:
            defects.append(
                f"{node.node_id}: parent_id {node.parent_id!r} does not exist "
                "in this tree."
            )

    leaves = tree.leaves()
    seen_tags: dict[str, str] = {}
    for leaf in leaves:
        prior = seen_tags.get(leaf.scope_tag)
        if prior is not None:
            defects.append(
                f"{leaf.node_id} and {prior} share scope_tag "
                f"{leaf.scope_tag!r} — leaves must partition the problem, "
                "not overlap it (Mutual Exclusivity violation)."
            )
        else:
            seen_tags[leaf.scope_tag] = leaf.node_id
        if not leaf.hypothesis_refs:
            defects.append(
                f"{leaf.node_id}: a leaf must reference at least one "
                "hypothesis — an unowned leaf is not Collectively Exhaustive, "
                "it's decoration."
            )
    return defects


# --- Hypothesis lifecycle ----------------------------------------------------------

# Below this confidence, a contradicted hypothesis is auto-retired rather than
# left open — a low-confidence, evidence-contradicted claim adds noise to the
# report, not signal, and holding onto it indefinitely is exactly the kind of
# unresolved dangling thread the Quant Gate philosophy exists to prevent.
_AUTO_RETIRE_THRESHOLD = 0.3


def evaluate_hypothesis(
    hypothesis: Hypothesis, store: EvidenceStore
) -> tuple[Hypothesis, list[str]]:
    """Recompute a hypothesis's status/confidence from its evidence links.

    ``status`` and ``confidence`` on the returned Hypothesis are ALWAYS
    computed here — an LLM's own claimed status/confidence is discarded, the
    same discipline P1 applies to a derived ledger value. Returns the
    recomputed hypothesis plus defect messages for any evidence reference that
    doesn't resolve in the Store (a dangling reference, not silently ignored).
    """
    defects: list[str] = []
    for atom_id in (
        *hypothesis.supporting_evidence,
        *hypothesis.contradicting_evidence,
    ):
        if store.get(atom_id) is None:
            defects.append(
                f"{hypothesis.hypothesis_id}: evidence reference {atom_id!r} "
                "does not exist in the Evidence Store."
            )

    n_support = len(hypothesis.supporting_evidence)
    n_contra = len(hypothesis.contradicting_evidence)
    total = n_support + n_contra
    confidence = n_support / total if total else 0.5

    if total == 0:
        status = "untested"
    elif n_contra > n_support:
        status = "contradicted"
    else:
        status = "supported"

    if status == "contradicted" and confidence < _AUTO_RETIRE_THRESHOLD:
        status = "retired"

    return replace(hypothesis, status=status, confidence=confidence), defects


# --- Research-plan coverage --------------------------------------------------------


def check_research_coverage(plan: ResearchPlan, tree: IssueTree) -> list[str]:
    """Every leaf in the issue tree needs an assigned research task — an
    unassigned leaf is a gap the pipeline would otherwise silently drop
    (mirrors the earlier, pre-ADR-009 failure mode of a leaf never getting
    closed and nobody noticing)."""
    gaps = plan.coverage(tree)
    return [
        f"issue node {node_id!r} has no assigned research task — every leaf "
        "must be covered or explicitly marked out of scope."
        for node_id in gaps
    ]


# --- Capability gating --------------------------------------------------------------


def check_capability_gate(
    option: StrategicOption, flags: list[CapabilityFlag]
) -> str | None:
    """Reject an option that depends on a capability explicitly flagged
    unavailable — the deterministic form of "is the client actually capable
    of executing this" (ADR-010's Capability Assessment goal). Returns a
    rejection reason, or None if the option clears every flagged capability
    it depends on. A capability with NO flag at all is not rejected — silence
    is not evidence of incapacity, only an explicit flag is."""
    unavailable = {f.capability for f in flags if not f.available}
    blocking = [c for c in option.required_capabilities if c in unavailable]
    if not blocking:
        return None
    reasons = "; ".join(
        next(f.rationale for f in flags if f.capability == c) or c for c in blocking
    )
    return (
        f"{option.option_id}: requires capability/ies {blocking} flagged "
        f"unavailable — {reasons}."
    )
