"""Evidence Normalizer (ADR-010 Phase 2, Task 2).

Deterministic, no-LLM-logic service. Analysts produce evidence atoms
independently (in parallel domains), so their raw output is inconsistent in
exactly the ways free text always is: one writes ``"$M"``, another
``"USD_M"``, another a bare percentage where a ratio is meant. This module
irons that out BEFORE atoms reach the Evidence Store, so the Store only ever
holds canonical, comparable values.

Nothing here calls an LLM or makes a judgment call about which VALUE is
correct when two analysts disagree — that stays the Engagement Manager's job
(unchanged from Phase 1). This module only canonicalizes REPRESENTATION
(units, currencies, percentages, confidence labels, obviously-identical
duplicates) so that when a real conflict exists, it becomes visible instead of
being an artifact of formatting differences.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from decimal import Decimal

from app.pipeline.evidence_schema import CONFIDENCE_LEVELS, EvidenceAtom

# --- unit / currency normalization -------------------------------------------

# Canonical currency-magnitude units the rest of the platform (quantcheck,
# ledger_builder) already uses unlabelled (EUR_M, USD_M, ...). Maps common
# analyst spellings/symbols onto that one canonical form per currency.
_CURRENCY_ALIASES: dict[str, str] = {
    "$m": "USD_M",
    "$mm": "USD_M",
    "usd m": "USD_M",
    "usd_m": "USD_M",
    "usd millions": "USD_M",
    "us$m": "USD_M",
    "€m": "EUR_M",
    "eur m": "EUR_M",
    "eur_m": "EUR_M",
    "eur millions": "EUR_M",
    "£m": "GBP_M",
    "gbp m": "GBP_M",
    "gbp_m": "GBP_M",
    "gbp millions": "GBP_M",
    "chf m": "CHF_M",
    "chf_m": "CHF_M",
}
_PERCENT_ALIASES = {"%", "pct", "percent", "percentage"}
_RATIO_ALIASES = {"ratio", "rate", "fraction"}


def normalize_unit(unit: str) -> str:
    """Canonicalize a unit string's spelling — never changes its MEANING.

    ``normalize_percentage`` (below) is what converts a PCT-denominated value
    into a RATIO; this function only fixes spelling (``"$M"`` -> ``"USD_M"``),
    so a currency unit and a percent/ratio unit are handled by two independent,
    single-purpose functions per the phase's design principle.
    """
    key = unit.strip().lower()
    if key in _CURRENCY_ALIASES:
        return _CURRENCY_ALIASES[key]
    if key in _PERCENT_ALIASES:
        return "PCT"
    if key in _RATIO_ALIASES:
        return "RATIO"
    # Already canonical-ish (e.g. "EUR_M", "COUNT", "EUR_BN") — just upper-case
    # for consistent comparison; unknown units pass through unchanged in shape.
    return unit.strip().upper().replace(" ", "_") if key else unit


def normalize_percentage(atom: EvidenceAtom) -> EvidenceAtom:
    """A PCT-denominated fact/assumption becomes a RATIO (value / 100).

    This is the same "RATIO never PCT in a formula" discipline quantcheck
    already enforces at verification time — doing it here means a percentage
    typo can never even reach the ledger, rather than being caught later.
    Derived atoms carry no value yet (P1's discipline), so there is nothing to
    convert; their unit is left as declared and checked at ledger-build time.

    The plausibility band travels WITH the value: converting ``value`` from
    20 to 0.20 while leaving ``low``/``high`` at 10/25 would make the atom
    fail its own band check (0.20 is not between 10 and 25) — a real bug this
    function must not introduce.
    """
    if atom.type == "derived" or atom.unit != "PCT" or atom.value is None:
        return atom
    return replace(
        atom,
        unit="RATIO",
        value=atom.value / Decimal(100),
        low=atom.low / Decimal(100) if atom.low is not None else None,
        high=atom.high / Decimal(100) if atom.high is not None else None,
    )


# --- confidence normalization -------------------------------------------------

_CONFIDENCE_ALIASES: dict[str, str] = {
    "high": "high",
    "strong": "high",
    "confident": "high",
    "very confident": "high",
    "medium": "medium",
    "med": "medium",
    "moderate": "medium",
    "low": "low",
    "weak": "low",
    "uncertain": "low",
    "speculative": "low",
}


def normalize_confidence(atom: EvidenceAtom) -> EvidenceAtom:
    """Map a synonym or a numeric 0-1 confidence onto the canonical 3-level
    scale. Confidence is advisory, not load-bearing for correctness — an
    unrecognized value degrades to 'medium' rather than failing the atom, in
    contrast to a value/unit problem, which schema-layer validation already
    rejected outright before this module ever sees the atom."""
    raw = atom.confidence.strip().lower()
    if raw in CONFIDENCE_LEVELS:
        return atom
    if raw in _CONFIDENCE_ALIASES:
        return replace(atom, confidence=_CONFIDENCE_ALIASES[raw])
    numeric = _as_float(raw)
    if numeric is not None:
        level = "high" if numeric >= 0.7 else "low" if numeric <= 0.3 else "medium"
        return replace(atom, confidence=level)
    return replace(atom, confidence="medium")


def _as_float(text: str) -> float | None:
    try:
        return float(text)
    except ValueError:
        return None


# --- alias resolution ---------------------------------------------------------

# Known synonyms across analyst domains for the same underlying concept. Keys
# and values are atom_id-shaped; resolution rewrites the KEY's occurrences (as
# an atom_id and inside any dependency/formula reference) onto the canonical
# VALUE, so two analysts naming the same thing differently still collide in
# the Store instead of silently duplicating it.
ALIAS_MAP: dict[str, str] = {
    "annual_revenue": "revenue",
    "total_revenue": "revenue",
    "net_revenue": "revenue",
    "opex": "operating_expense",
    "operating_expenses": "operating_expense",
    "cogs": "cost_of_goods_sold",
    "ebitda_margin_pct": "ebitda_margin",
}

_NORMALIZE_TITLE_RE = re.compile(r"[^a-z0-9]+")


def _title_key(title: str) -> str:
    return _NORMALIZE_TITLE_RE.sub("_", title.strip().lower()).strip("_")


def resolve_aliases(
    atoms: list[EvidenceAtom],
) -> tuple[list[EvidenceAtom], dict[str, str]]:
    """Rewrite each atom's id (and every dependency/formula reference to it)
    onto a canonical id, via the explicit :data:`ALIAS_MAP` first and a
    normalized-title match second (e.g. "Annual Revenue" and "Total Revenue"
    both collapse onto whichever canonical id appears first).

    Returns the rewritten atoms and the id-rewrite map applied (old -> new),
    so callers (and tests) can see exactly what was merged and why.
    """
    rewrite: dict[str, str] = {}
    title_seen: dict[str, str] = {}
    for atom in atoms:
        canonical = ALIAS_MAP.get(atom.atom_id)
        if canonical is None:
            tkey = _title_key(atom.title)
            canonical = title_seen.setdefault(tkey, atom.atom_id)
        if canonical != atom.atom_id:
            rewrite[atom.atom_id] = canonical

    if not rewrite:
        return atoms, rewrite

    def _apply(atom_id: str) -> str:
        return rewrite.get(atom_id, atom_id)

    out: list[EvidenceAtom] = []
    for atom in atoms:
        new_formula = atom.formula
        if new_formula:
            for old, new in rewrite.items():
                new_formula = re.sub(rf"\b{re.escape(old)}\b", new, new_formula)
        out.append(
            replace(
                atom,
                atom_id=_apply(atom.atom_id),
                dependencies=tuple(_apply(d) for d in atom.dependencies),
                formula=new_formula,
                anchor=_apply(atom.anchor) if atom.anchor else None,
            )
        )
    return out, rewrite


# --- duplicate / conflict resolution ------------------------------------------


def _fingerprint(atom: EvidenceAtom) -> tuple[object, ...]:
    """Everything that makes an atom's DEFINITION distinct, not just its id
    and headline value.

    Real bug, found by an external Codex review and confirmed by
    reproduction before fixing: the original fingerprint omitted ``scope``
    and the ``low``/``high`` band, so two atoms with the same id and value
    but a DIFFERENT time scope (e.g. "annual" vs "cumulative_3yr") or a
    different plausibility band were treated as identical duplicates —
    ``dedupe()`` silently collapsed them onto whichever arrived first instead
    of surfacing a genuine semantic conflict for the Engagement Manager to
    resolve.
    """
    return (
        atom.atom_id,
        atom.type,
        atom.unit,
        atom.scope,
        atom.value,
        atom.formula,
        atom.low,
        atom.high,
    )


def dedupe(atoms: list[EvidenceAtom]) -> tuple[list[EvidenceAtom], list[str]]:
    """Collapse atoms that are identical after alias resolution; flag (but do
    NOT silently overwrite) atoms that share an id with a DIFFERENT
    definition — that is a genuine cross-analyst disagreement, and per the
    phase's design principle this module makes it visible rather than
    adjudicating it. Both conflicting atoms are kept, tagged
    ``status="conflict"``, so the Engagement Manager (unchanged from Phase 1)
    still does the one job that requires judgment: picking the authoritative
    value.
    """
    by_id: dict[str, EvidenceAtom] = {}
    warnings: list[str] = []
    for atom in atoms:
        existing = by_id.get(atom.atom_id)
        if existing is None:
            by_id[atom.atom_id] = atom
            continue
        if _fingerprint(existing) == _fingerprint(atom):
            continue  # identical from another analyst — silently collapses
        warnings.append(
            f"conflict on '{atom.atom_id}': {existing.created_by} says "
            f"{existing.value}{existing.unit}, {atom.created_by} says "
            f"{atom.value}{atom.unit} — left for the Engagement Manager to "
            "resolve."
        )
        by_id[atom.atom_id] = replace(existing, status="conflict")
        by_id[f"{atom.atom_id}__{atom.created_by}"] = replace(atom, status="conflict")
    return list(by_id.values()), warnings


# --- entry point ---------------------------------------------------------------


@dataclass(frozen=True)
class NormalizeResult:
    atoms: tuple[EvidenceAtom, ...]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    rewritten_ids: dict[str, str]


def normalize(atoms: list[EvidenceAtom]) -> NormalizeResult:
    """Run the full normalization pipeline: unit/currency spelling, percentage
    to ratio conversion, confidence canonicalization, alias resolution, then
    duplicate/conflict detection. Order matters — percentages and units are
    normalized per-atom BEFORE alias merging, so two analysts' "20%" and "0.20
    RATIO" for the same aliased concept compare equal rather than falsely
    conflicting on representation alone.
    """
    step1 = [replace(a, unit=normalize_unit(a.unit)) for a in atoms]
    step2 = [normalize_percentage(a) for a in step1]
    step3 = [normalize_confidence(a) for a in step2]
    aliased, rewritten = resolve_aliases(step3)
    deduped, warnings = dedupe(aliased)
    validated = [replace(a, validation_state="normalized") for a in deduped]
    return NormalizeResult(tuple(validated), tuple(warnings), (), rewritten)
