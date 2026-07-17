"""Sensitivity Analysis (ADR-010 Phase 3) — reuses P1's ledger arithmetic.

"Which assumption would flip the recommendation" is answered mechanically,
not narrated: for every assumption in an already Quant-Gate-verified ledger,
every derived value that depends on it (directly or transitively) is
recomputed at the assumption's stated ``low`` and ``high`` bound, using the
exact same :func:`quantcheck._eval` the gate itself uses. The result is a
ranked list of swings — zero new LLM calls, zero new judgment, a pure
function of a ledger that has already been proven internally consistent.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from app.pipeline.consulting_schema import SensitivityResult
from app.pipeline.quantcheck import Entry, _eval, _parse_formula


def _topo_order(entries: Mapping[str, Entry]) -> list[str]:
    """Derived entries in dependency order. The ledger has already passed the
    Quant Gate (acyclic, by construction) — this is a fixed-point pass, not a
    full cycle-safe sort, because cycles are already ruled out upstream."""
    derived = [eid for eid, e in entries.items() if e.formula]
    ordered: list[str] = []
    done: set[str] = {eid for eid, e in entries.items() if not e.formula}
    remaining = list(derived)
    while remaining:
        progressed = False
        for eid in list(remaining):
            inputs = entries[eid].inputs
            if all(i in done or i not in entries for i in inputs):
                ordered.append(eid)
                done.add(eid)
                remaining.remove(eid)
                progressed = True
        if not progressed:
            break  # a cycle would land here; upstream verification prevents it
    return ordered


def recompute_all(
    entries: Mapping[str, Entry], overrides: Mapping[str, Decimal]
) -> dict[str, Decimal]:
    """Every entry's value with ``overrides`` substituted for the given ids,
    propagated through every derived entry in dependency order."""
    values: dict[str, Decimal] = {
        eid: overrides.get(eid, e.value) for eid, e in entries.items() if not e.formula
    }
    for eid in _topo_order(entries):
        entry = entries[eid]
        assert entry.formula is not None
        try:
            tree = _parse_formula(entry.formula)
            values[eid] = _eval(tree, values)
        except Exception:  # noqa: BLE001 - a formula that can't re-evaluate is
            # excluded from this entry's swing rather than crashing the whole
            # analysis; the Quant Gate already guarantees it evaluates under
            # the BASE values, so this only affects an extreme override.
            continue
    return values


def analyze_sensitivity(
    entries: Mapping[str, Entry],
) -> list[SensitivityResult]:
    """One :class:`SensitivityResult` per assumption with a plausibility band,
    ranked by swing magnitude (largest first) — the "what would change the
    answer" the Challenger agent is asked to reason about qualitatively, made
    quantitative and exact.
    """
    base_values = {eid: e.value for eid, e in entries.items()}
    results: list[SensitivityResult] = []

    for eid, entry in entries.items():
        if entry.kind != "assumption" or entry.low is None or entry.high is None:
            continue

        low_values = recompute_all(entries, {eid: entry.low})
        high_values = recompute_all(entries, {eid: entry.high})

        affected: list[str] = []
        max_swing = Decimal(0)
        for other_id, other in entries.items():
            if other.formula is None or other_id not in low_values:
                continue
            base = base_values.get(other_id)
            if base is None:
                continue
            swing = max(
                abs(low_values[other_id] - base),
                abs(high_values.get(other_id, base) - base),
            )
            if swing != 0:
                affected.append(other_id)
                max_swing = max(max_swing, swing)

        if affected:
            results.append(
                SensitivityResult(
                    assumption_id=eid,
                    low_value=entry.low,
                    high_value=entry.high,
                    affected=tuple(sorted(affected)),
                    swing=max_swing,
                )
            )

    return sorted(results, key=lambda r: r.swing, reverse=True)
