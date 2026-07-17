"""Deterministic Ledger Builder (ADR-010 Phase 1).

The single biggest defect in the pipeline was that an LLM (the Engagement
Manager) hand-authored the whole ``quant`` ledger — 30-50 rows of JSON with
unique ids, wired formulas, and consistent units — which free-tier models could
not do reliably (7/7 live Quant Gate failures). The v2.0 principle is blunt:
*LLMs must not invent calculations, and no LLM may generate the ledger.*

So the division of labour changes. The LLM emits typed **evidence atoms** — the
part it is good at (this metric is worth ~X, sourced from Y, and is delivery ×
commission × revenue). This module — deterministic code — does the part the LLM
is bad at:

* mints canonical, unique ids (A-n for fact/assumption, D-n for derived);
* translates each derived atom's key-referenced expression into the id-based
  formula the verifier consumes (so a formula can never reference a dangling or
  wrong id — the #1 structural failure);
* **computes every derived value itself** from the atoms' formulas, in exact
  ``Decimal`` arithmetic (the LLM's stated value for a derived row is ignored —
  it cannot inject a wrong calculation);
* emits the ``quant`` JSON block that :mod:`app.pipeline.quantcheck` then
  verifies exactly as before.

The Quant Gate (ADR-009) remains the proof of correctness; this module removes
the structural class of failure *upstream* of it, so the gate is left to check
the things that still depend on the analyst's judgement (units, plausibility
bands, bridge closure, fact anchors) rather than failing on malformed JSON.

Backward compatible: if a reconciliation contains no ``atoms`` block, the input
is returned untouched (any LLM-authored ``quant`` block flows through as before).
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

# Tightly-coupled sibling module: reuse the verifier's validated formula parser
# and evaluator so "the arithmetic" is defined in exactly one place.
from app.pipeline.quantcheck import (
    _eval,
    _formula_ids,
    _FormulaError,
    _parse_formula,
    dump_decimal_json,
)

_KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_ATOMS_BLOCK_RE = re.compile(r"```atoms\s*\n(.*?)```", re.S)
_QUANT_BLOCK_RE = re.compile(r"```quant\s*\n.*?```", re.S)

_KINDS = ("fact", "assumption", "derived")


@dataclass(frozen=True)
class BuildResult:
    """Outcome of assembling a ledger from atoms.

    ``markdown`` is the reconciliation text with a freshly-built, correct
    ``quant`` block appended (and any prior one stripped). ``errors`` are exact,
    actionable messages for the rework loop — empty on success. ``had_atoms`` is
    False when there was nothing to build (no ``atoms`` block), in which case the
    input passes through unchanged.
    """

    markdown: str
    errors: tuple[str, ...]
    had_atoms: bool


@dataclass
class _Atom:
    key: str
    kind: str
    label: str
    unit: str
    scope: str
    value: Decimal | None
    source: str | None
    low: Decimal | None
    high: Decimal | None
    expr: str | None
    anchor: str | None
    bridge: bool


def build_from_markdown(reconciliation: str) -> BuildResult:
    """Extract the ``atoms`` block from an EM reconciliation and build the ledger.

    No atoms block → pass-through (``had_atoms=False``, no errors). Malformed
    atoms → ``errors`` for the rework loop and the original text unchanged so the
    caller can re-dispatch. Success → the text with a correct ``quant`` block.

    Uses the LAST ``atoms`` block, not the first (real bug, found by an
    external Codex review and confirmed by reproduction before fixing): the
    engine's rework prompt literally quotes "Your previous canonical
    reconciliation" — including its stale ```atoms block — ahead of asking
    for the correction, so a naive first-match extraction silently rebuilds
    the ledger from the OLD, pre-correction values on every rework. Mirrors
    quantcheck.extract_block's existing "last block wins" discipline, which
    this module should have replicated from the start.
    """
    blocks = _ATOMS_BLOCK_RE.findall(reconciliation)
    if not blocks:
        return BuildResult(reconciliation, (), had_atoms=False)

    block, errors = _build_block(blocks[-1])
    if errors:
        return BuildResult(reconciliation, tuple(errors), had_atoms=True)

    # Strip any LLM-authored quant block; append the deterministic one.
    body = _QUANT_BLOCK_RE.sub("", reconciliation).rstrip()
    rebuilt = f"{body}\n\n```quant\n{block}\n```\n"
    return BuildResult(rebuilt, (), had_atoms=True)


def _build_block(raw: str) -> tuple[str, list[str]]:
    """Parse atoms JSON → emit the quant-ledger JSON block (or errors)."""
    try:
        data = json.loads(raw, parse_float=Decimal, parse_int=Decimal)
    except json.JSONDecodeError as exc:
        return "", [
            f"atoms block is not valid JSON: {exc.msg} at line {exc.lineno}, "
            f"column {exc.colno}. Emit a single JSON array of atom objects."
        ]
    if isinstance(data, dict):
        data = data.get("atoms")
    if not isinstance(data, list) or not data:
        return "", [
            "atoms block must be a non-empty JSON array of atom objects "
            '(or {"atoms": [...]}).'
        ]

    atoms, errors = _parse_atoms(data)
    if errors:
        return "", errors

    by_key = {a.key: a for a in atoms}
    order, cycle_err = _topo_order(atoms, by_key)
    if cycle_err:
        return "", cycle_err

    # Canonical ids: facts/assumptions get A-n, derived get D-n, both in the
    # atoms' declared order so ids are stable and human-readable.
    key_to_id: dict[str, str] = {}
    a_n = d_n = 0
    for atom in atoms:
        if atom.kind == "derived":
            d_n += 1
            key_to_id[atom.key] = f"D{d_n}"
        else:
            a_n += 1
            key_to_id[atom.key] = f"A{a_n}"

    values: dict[str, Decimal] = {}
    entries: list[dict[str, object]] = []

    # Non-derived first so their values are available to derived evaluation.
    for atom in atoms:
        if atom.kind != "derived":
            assert atom.value is not None  # guaranteed by _parse_atoms
            values[key_to_id[atom.key]] = atom.value
            entries.append(_leaf_entry(atom, key_to_id[atom.key]))

    # Derived in dependency order: compute the value here — never trust the LLM's.
    for key in order:
        atom = by_key[key]
        if atom.kind != "derived":
            continue
        entry, err = _derived_entry(atom, key_to_id, values)
        if err:
            return "", [err]
        entries.append(entry)

    return dump_decimal_json(entries), []


def _parse_atoms(data: list[object]) -> tuple[list[_Atom], list[str]]:
    atoms: list[_Atom] = []
    errors: list[str] = []
    seen: dict[str, _Atom] = {}
    for i, raw in enumerate(data):
        if not isinstance(raw, dict):
            errors.append(f"atom #{i + 1} is not an object.")
            continue
        key = raw.get("key")
        if not isinstance(key, str) or not _KEY_RE.match(key):
            errors.append(
                f"atom #{i + 1}: 'key' must be a slug (letters/digits/underscore, "
                f"starting with a letter), got {key!r}."
            )
            continue
        kind = raw.get("kind")
        if kind not in _KINDS:
            errors.append(f"{key}: 'kind' must be one of {_KINDS}, got {kind!r}.")
            continue
        unit = raw.get("unit")
        if not isinstance(unit, str) or not unit:
            errors.append(f"{key}: 'unit' is required (e.g. EUR_M, RATIO, PCT).")
            continue
        value = _as_decimal(raw.get("value"))
        low, high = _as_decimal(raw.get("low")), _as_decimal(raw.get("high"))
        expr = raw.get("expr")
        atom = _Atom(
            key=key,
            kind=kind,
            label=str(raw.get("label") or key),
            unit=unit,
            scope=str(raw.get("scope") or ""),
            value=value,
            source=(raw.get("source") if isinstance(raw.get("source"), str) else None),
            low=low,
            high=high,
            expr=expr if isinstance(expr, str) and expr.strip() else None,
            anchor=(raw.get("anchor") if isinstance(raw.get("anchor"), str) else None),
            bridge=raw.get("bridge") is True,
        )

        per_kind = _validate_atom(atom)
        if per_kind:
            errors.append(per_kind)
            continue

        if key in seen:
            # Identical re-declaration collapses; a conflicting one is an error.
            if _atoms_conflict(seen[key], atom):
                errors.append(
                    f"{key}: declared twice with different definitions — give "
                    "each metric one atom, or one key per distinct metric."
                )
            continue
        seen[key] = atom
        atoms.append(atom)
    return atoms, errors


def _validate_atom(atom: _Atom) -> str | None:
    if atom.kind == "derived":
        if not atom.expr:
            return (
                f"{atom.key}: a derived atom needs an 'expr' over other atom keys "
                "(its value is computed for you — do not state one)."
            )
        return None
    # fact / assumption
    if atom.value is None or not atom.value.is_finite():
        return f"{atom.key}: a {atom.kind} needs a finite numeric 'value'."
    if atom.expr:
        return f"{atom.key}: only a derived atom may carry an 'expr'."
    if not atom.source:
        return (
            f"{atom.key}: a {atom.kind} must state its 'source' "
            "(client_fact, benchmark, or analyst_estimate)."
        )
    if atom.kind == "assumption" and (atom.low is None or atom.high is None):
        return f"{atom.key}: an assumption must declare a 'low'/'high' band."
    return None


def _atoms_conflict(a: _Atom, b: _Atom) -> bool:
    """True if two same-key atoms differ in ANY ledger-affecting field.

    Real bug, found by an external Codex review and confirmed by
    reproduction before fixing: the original comparison omitted
    low/high/anchor/bridge, so two declarations with the same value but a
    DIFFERENT plausibility band (or anchor/bridge flag) were treated as
    identical — the second, possibly tighter or more correct declaration was
    silently dropped instead of being surfaced as a conflict.
    """
    return (
        a.kind,
        a.unit,
        a.scope,
        a.value,
        a.expr,
        a.low,
        a.high,
        a.anchor,
        a.bridge,
    ) != (
        b.kind,
        b.unit,
        b.scope,
        b.value,
        b.expr,
        b.low,
        b.high,
        b.anchor,
        b.bridge,
    )


def _leaf_entry(atom: _Atom, entry_id: str) -> dict[str, object]:
    entry: dict[str, object] = {
        "id": entry_id,
        "kind": atom.kind,
        "label": atom.label,
        "value": atom.value,
        "unit": atom.unit,
        "basis": {"scope": atom.scope} if atom.scope else {"scope": ""},
        "source": atom.source,
    }
    if atom.kind == "assumption":
        entry["low"] = atom.low
        entry["high"] = atom.high
    return entry


def _derived_entry(
    atom: _Atom,
    key_to_id: dict[str, str],
    values: dict[str, Decimal],
) -> tuple[dict[str, object], str | None]:
    assert atom.expr is not None
    try:
        tree = _parse_formula(atom.expr)
    except _FormulaError as exc:
        return {}, f"{atom.key}: {exc}"
    ref_keys = _formula_ids(tree)
    if not ref_keys:
        return {}, (
            f"{atom.key}: expr {atom.expr!r} references no other atom — a "
            "constant is a fact, not a derived value."
        )
    missing = [k for k in ref_keys if k not in key_to_id]
    if missing:
        return {}, (
            f"{atom.key}: expr references unknown atom key(s) {missing} — every "
            "name in an expr must be another atom's key."
        )
    # Rewrite key-refs → canonical ids, then compute the value ourselves.
    id_tree = _RenameKeys(key_to_id).visit(tree)
    id_formula = ast.unparse(id_tree)
    try:
        computed = _eval(ast.parse(id_formula, mode="eval"), values)
    except (_FormulaError, ArithmeticError, InvalidOperation) as exc:
        return {}, f"{atom.key}: could not evaluate expr — {exc}"
    values[key_to_id[atom.key]] = computed

    entry: dict[str, object] = {
        "id": key_to_id[atom.key],
        "kind": "derived",
        "label": atom.label,
        "value": computed,
        "unit": atom.unit,
        "basis": {"scope": atom.scope} if atom.scope else {"scope": ""},
        "formula": id_formula,
    }
    if atom.anchor:
        anchor_id = key_to_id.get(atom.anchor)
        if anchor_id is None:
            return {}, (f"{atom.key}: anchor '{atom.anchor}' is not an atom key.")
        entry["anchor"] = anchor_id
    if atom.bridge:
        entry["bridge"] = True
    return entry, None


class _RenameKeys(ast.NodeTransformer):
    """Rewrite ``Name`` nodes from an atom key to its canonical ledger id."""

    def __init__(self, key_to_id: dict[str, str]) -> None:
        self._map = key_to_id

    def visit_Name(self, node: ast.Name) -> ast.Name:
        return ast.copy_location(
            ast.Name(id=self._map.get(node.id, node.id), ctx=node.ctx), node
        )


def _topo_order(
    atoms: list[_Atom], by_key: dict[str, _Atom]
) -> tuple[list[str], list[str]]:
    """Dependency order over derived atoms; reports a cycle as an error list."""
    WHITE, GREY, BLACK = 0, 1, 2
    color = {a.key: WHITE for a in atoms}
    order: list[str] = []
    errors: list[str] = []

    def deps(atom: _Atom) -> list[str]:
        if atom.kind != "derived" or not atom.expr:
            return []
        try:
            return [k for k in _formula_ids(_parse_formula(atom.expr)) if k in by_key]
        except _FormulaError:
            return []

    def visit(key: str, path: list[str]) -> None:
        color[key] = GREY
        path.append(key)
        for dep in deps(by_key[key]):
            if color[dep] == GREY:
                cyc = path[path.index(dep) :] + [dep]
                errors.append(
                    "circular derivation: "
                    + " -> ".join(cyc)
                    + " — an atom may not depend on itself."
                )
            elif color[dep] == WHITE:
                visit(dep, path)
        path.pop()
        color[key] = BLACK
        order.append(key)

    for atom in atoms:
        if color[atom.key] == WHITE:
            visit(atom.key, [])
    return order, errors


def _as_decimal(raw: object) -> Decimal | None:
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, Decimal):
        return raw
    if isinstance(raw, int):
        return Decimal(raw)
    return None


def format_errors(errors: tuple[str, ...]) -> str:
    return "\n".join(f"{i}. {e}" for i, e in enumerate(errors, 1))
