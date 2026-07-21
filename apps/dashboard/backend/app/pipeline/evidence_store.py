"""Evidence Store (ADR-010 Phase 2, Task 3).

The canonical, in-memory repository for one engagement's normalized evidence.
Everything downstream — today, the Engagement Manager's reconciliation and
Phase 1's Ledger Builder — consumes THIS, never a raw analyst response
directly (Task 6's "no downstream component should consume raw analyst
output").

Scope note: this is a per-engagement, in-process store (built fresh for each
run's analysis phase and discarded after reconciliation), not a persisted
table. Persisting the evidence lifecycle durably across engagements is a
larger, separate decision (a DB migration, a retention policy, a query
surface) that Phase 2 deliberately does not take on — the spec's own
instruction is to focus exclusively on the evidence platform, and persistence
is not required for the Store to do its job of aggregating and serving one
engagement's atoms to the Ledger Builder.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.pipeline.evidence_schema import EvidenceAtom
from app.pipeline.quantcheck import dump_decimal_json


@dataclass(frozen=True)
class Provenance:
    created_by: str
    source_type: str | None
    source_reference: str


class EvidenceStore:
    """Canonical repository: versioning, dedup, and lookup by id / category /
    dependency / source, plus confidence, assumption, and provenance tracking.

    Atoms arriving here are assumed already normalized (``evidence_normalizer``
    has run) — the Store's job is aggregation and retrieval, not validation.
    Because the normalizer deliberately preserves BOTH sides of a genuine
    cross-analyst conflict (rather than silently picking one), the Store is a
    multimap (``atom_id -> [atoms]``): ``get`` returns a single representative
    atom for the common case, ``get_all`` exposes every atom sharing an id
    when a conflict needs to be seen.
    """

    def __init__(self) -> None:
        self._by_id: dict[str, list[EvidenceAtom]] = {}
        self._order: list[str] = []  # first-seen order, for stable rendering

    def add(self, atom: EvidenceAtom) -> None:
        if atom.atom_id not in self._by_id:
            self._by_id[atom.atom_id] = []
            self._order.append(atom.atom_id)
        self._by_id[atom.atom_id].append(atom)

    def add_many(self, atoms: list[EvidenceAtom]) -> None:
        for atom in atoms:
            self.add(atom)

    # --- lookup -----------------------------------------------------------

    def get(self, atom_id: str) -> EvidenceAtom | None:
        """The first atom stored under this id (deterministic: insertion
        order). Use :meth:`get_all` to see every atom in a conflict."""
        atoms = self._by_id.get(atom_id)
        return atoms[0] if atoms else None

    def get_all(self, atom_id: str) -> list[EvidenceAtom]:
        return list(self._by_id.get(atom_id, []))

    def all(self) -> list[EvidenceAtom]:
        return [a for atom_id in self._order for a in self._by_id[atom_id]]

    def by_category(self, category: str) -> list[EvidenceAtom]:
        return [a for a in self.all() if a.category == category]

    def by_source(self, source_type: str) -> list[EvidenceAtom]:
        return [a for a in self.all() if a.source_type == source_type]

    def dependents_of(self, atom_id: str) -> list[EvidenceAtom]:
        """Every atom whose ``dependencies``, ``formula``, or ``anchor``
        references ``atom_id`` — the reverse-dependency lookup Task 3 asks
        for, used e.g. to explain "what breaks if this assumption changes"."""
        out = []
        for atom in self.all():
            referenced = atom_id in atom.dependencies or atom.anchor == atom_id
            if not referenced and atom.formula:
                referenced = _references(atom.formula, atom_id)
            if referenced:
                out.append(atom)
        return out

    # --- tracking -----------------------------------------------------------

    def assumptions(self) -> list[EvidenceAtom]:
        return [a for a in self.all() if a.type == "assumption"]

    def conflicts(self) -> list[EvidenceAtom]:
        return [a for a in self.all() if a.status == "conflict"]

    def confidence_summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for atom in self.all():
            counts[atom.confidence] = counts.get(atom.confidence, 0) + 1
        return counts

    def provenance(self, atom_id: str) -> list[Provenance]:
        return [
            Provenance(a.created_by, a.source_type, a.source_reference)
            for a in self.get_all(atom_id)
        ]

    # --- bridge to Phase 1 (unchanged) ---------------------------------------

    def to_atoms_block(self) -> str:
        """Render the store's atoms as the exact ``atoms`` JSON array Phase
        1's ``ledger_builder.build_from_markdown`` already parses — this is
        the whole point of the Store existing: the Ledger Builder is reused
        completely unmodified (Task 3's "everything downstream must consume
        this store" + the phase's "do not duplicate functionality").

        A conflicting id (more than one atom under the same key) is rendered
        with EACH atom under a disambiguated key (``id__creator``), exactly as
        the normalizer already does internally — the Engagement Manager still
        sees both values and still does the one job requiring judgment:
        picking the authoritative one. That EM step is unchanged from Phase 1.
        """
        rows: list[dict[str, object]] = []
        for atom_id in self._order:
            group = self._by_id[atom_id]
            for atom in group:
                key = atom_id if len(group) == 1 else f"{atom_id}__{atom.created_by}"
                rows.append(_to_atom_row(atom, key))
        block: str = dump_decimal_json(rows)
        return block

    def __len__(self) -> int:
        return len(self.all())


def _references(expr: str, atom_id: str) -> bool:
    return re.search(rf"\b{re.escape(atom_id)}\b", expr) is not None


def _to_atom_row(atom: EvidenceAtom, key: str) -> dict[str, object]:
    row: dict[str, object] = {
        "key": key,
        "kind": atom.type,
        "label": atom.title,
        "unit": atom.unit,
    }
    if atom.scope:
        row["scope"] = atom.scope
    if atom.type == "derived":
        row["expr"] = atom.formula
    elif atom.type == "unknown":
        # ledger_builder's "unknown" kind expects the rationale under
        # `source` (matching fact/assumption's field name) — evidence_schema
        # carries it as `description`, so bridge the two field names here
        # rather than at the analyst-facing schema or the EM-facing ledger
        # builder, keeping each module's own field naming intact.
        row["source"] = atom.description or "no rationale given"
    else:
        row["value"] = atom.value
        row["source"] = atom.source_type
        if atom.low is not None:
            row["low"] = atom.low
        if atom.high is not None:
            row["high"] = atom.high
    if atom.anchor:
        row["anchor"] = atom.anchor
    if atom.bridge:
        row["bridge"] = True
    return row


def build_store(atoms: list[EvidenceAtom]) -> EvidenceStore:
    store = EvidenceStore()
    store.add_many(atoms)
    return store
