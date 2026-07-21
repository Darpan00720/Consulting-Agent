"""Canonical Evidence Schema (ADR-010 Phase 2, Task 1).

Phase 1 (``ledger_builder.py``) fixed the Engagement Manager's ledger authoring
by having it emit typed ``atoms`` instead of hand-wiring a JSON ledger. Phase 2
pushes that one step further upstream: each ANALYST emits its own typed
evidence directly, in its own domain, instead of free-form prose the EM later
has to re-derive atoms from. This module is the schema that evidence.

Versioned on purpose (``SCHEMA_VERSION``): the fields below are v1. A future
version may add fields, but must not repurpose or remove existing ones, so a
v1 atom always remains readable by v2+ code (see ``migration strategy`` in
ADR-010 §P2).

This module does ONE thing: parse and structurally validate a raw ``evidence``
block into a list of :class:`EvidenceAtom`. It does not normalize (that is
``evidence_normalizer.py``, deliberately a separate module with zero LLM logic
of its own) and does not aggregate across analysts (``evidence_store.py``).
Single responsibility, per the phase's own design principle.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from decimal import Decimal

from app.pipeline.quantcheck import _formula_ids, _FormulaError, _parse_formula

SCHEMA_VERSION = 1

# The exact field set a v1 atom may carry. Reusing the P1 slug pattern for
# atom_id/dependencies means an EvidenceAtom's id is ALWAYS already a valid
# ledger_builder key — the Evidence Store's bridge to P1 (Task 3) needs no
# further sanitization or remapping.
_SLUG_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")

CATEGORIES = ("financial", "market", "operational", "strategic", "risk", "general")
TYPES = ("fact", "assumption", "derived", "unknown")
CONFIDENCE_LEVELS = ("high", "medium", "low")
SOURCE_TYPES = ("client_fact", "benchmark", "analyst_estimate", "external_research")
VALIDATION_STATES = ("unvalidated", "normalized", "validated", "rejected")
STATUSES = ("open", "resolved", "conflict", "superseded")

# The full v1 field set — Task 5 requires rejecting UNKNOWN fields, which is
# only meaningful against an explicit allow-list. NOTE: "scope" is not in the
# v2.0 spec's example field list, but is added deliberately here: P1's Quant
# Gate (ADR-009) uses a time-basis scope ("annual" vs "cumulative_3yr", ...) to
# catch basis-mixing errors, and the spec's own principle is to "reuse ADR-009
# and Phase 1" — dropping scope would make the Store -> Ledger Builder bridge
# LOSSY relative to what P1 already verifies, so this is a justified, minimal
# extension of the example list rather than a deviation from it.
_ALLOWED_FIELDS = frozenset(
    {
        "schema_version",
        "atom_id",
        "category",
        "type",
        "title",
        "description",
        "value",
        "unit",
        "scope",
        "confidence",
        "confidence_reason",
        "source_type",
        "source_reference",
        "assumptions",
        "dependencies",
        "formula",
        "low",
        "high",
        "anchor",
        "bridge",
    }
)
# Required regardless of type.
_ALWAYS_REQUIRED = ("atom_id", "category", "type", "title", "unit")


@dataclass(frozen=True)
class EvidenceAtom:
    """One canonical, versioned, machine-readable evidence record.

    ``value``/``formula`` follow the same discipline P1 introduced: a
    ``derived`` atom carries a ``formula`` over other atoms' ``atom_id``s and
    NEVER a ``value`` — the platform computes it, never trusts an LLM's
    arithmetic. A ``fact``/``assumption`` carries ``value`` and never
    ``formula``.
    """

    schema_version: int
    atom_id: str
    category: str
    type: str  # noqa: A003 - "type" is the schema's field name, not shadowing
    title: str
    unit: str
    scope: str = ""  # time basis: "annual", "cumulative_3yr", ... (see NOTE above)
    description: str = ""
    value: Decimal | None = None
    confidence: str = "medium"
    confidence_reason: str = ""
    source_type: str | None = None
    source_reference: str = ""
    assumptions: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    formula: str | None = None
    low: Decimal | None = None
    high: Decimal | None = None
    anchor: str | None = None
    bridge: bool = False
    created_by: str = ""
    created_at: float = field(default_factory=time.time)
    validation_state: str = "unvalidated"
    status: str = "open"


@dataclass(frozen=True)
class ParseResult:
    atoms: tuple[EvidenceAtom, ...]
    errors: tuple[str, ...]


_EVIDENCE_BLOCK_RE = re.compile(r"```evidence\s*\n(.*?)```", re.S)


def extract_evidence_block(markdown: str) -> str | None:
    """The LAST ```evidence block (a rework response may quote an earlier one)."""
    blocks = _EVIDENCE_BLOCK_RE.findall(markdown)
    return blocks[-1] if blocks else None


def parse_evidence_block(markdown: str, created_by: str) -> ParseResult:
    """Extract and structurally validate one analyst's ``evidence`` block.

    ``created_by`` is the analyst agent name — stamped onto every atom as
    provenance (Task 3's "provenance tracking" starts here, not as an
    afterthought). Returns atoms plus exact, actionable error strings; a
    non-empty ``errors`` means the WHOLE block is rejected (an analyst's
    evidence is all-or-nothing, so a partially-malformed block can never
    silently drop one bad atom into the store).
    """
    block = extract_evidence_block(markdown)
    if block is None:
        return ParseResult((), ())  # no evidence block: legacy/prose fallback

    try:
        data = json.loads(block, parse_float=Decimal, parse_int=Decimal)
    except json.JSONDecodeError as exc:
        return ParseResult(
            (),
            (
                f"{created_by}: evidence block is not valid JSON: {exc.msg} at "
                f"line {exc.lineno}, column {exc.colno}.",
            ),
        )
    if isinstance(data, dict):
        data = data.get("atoms")
    if not isinstance(data, list) or not data:
        return ParseResult(
            (),
            (f"{created_by}: evidence block must be a non-empty JSON array.",),
        )

    atoms: list[EvidenceAtom] = []
    errors: list[str] = []
    seen_ids: set[str] = set()
    for i, raw in enumerate(data):
        if not isinstance(raw, dict):
            errors.append(f"{created_by}: atom #{i + 1} is not an object.")
            continue
        atom, err = _parse_one(raw, created_by, i + 1)
        if err:
            errors.append(err)
            continue
        assert atom is not None
        if atom.atom_id in seen_ids:
            errors.append(
                f"{created_by}: duplicate atom_id {atom.atom_id!r} within one "
                "analyst's own evidence block."
            )
            continue
        seen_ids.add(atom.atom_id)
        atoms.append(atom)

    if errors:
        return ParseResult((), tuple(errors))
    return ParseResult(tuple(atoms), ())


def _parse_one(
    raw: dict[str, object], created_by: str, position: int
) -> tuple[EvidenceAtom | None, str | None]:
    tag = f"{created_by} atom #{position}"

    unknown = set(raw) - _ALLOWED_FIELDS
    if unknown:
        return None, f"{tag}: unknown field(s) {sorted(unknown)}."

    missing = [f for f in _ALWAYS_REQUIRED if not raw.get(f)]
    if missing:
        return None, f"{tag}: missing required field(s) {missing}."

    atom_id = raw["atom_id"]
    if not isinstance(atom_id, str) or not _SLUG_RE.match(atom_id):
        return None, (
            f"{tag}: atom_id must be a slug (letters/digits/underscore, "
            f"starting with a letter), got {atom_id!r}."
        )
    category = raw["category"]
    if category not in CATEGORIES:
        return None, f"{tag} ({atom_id}): category must be one of {CATEGORIES}."
    kind = raw["type"]
    if kind not in TYPES:
        return None, f"{tag} ({atom_id}): type must be one of {TYPES}."
    title = raw["title"]
    if not isinstance(title, str):
        return None, f"{tag} ({atom_id}): title must be a string."
    unit = raw["unit"]
    if not isinstance(unit, str):
        return None, f"{tag} ({atom_id}): unit must be a string."
    scope = raw.get("scope", "")
    if not isinstance(scope, str):
        return None, f"{tag} ({atom_id}): scope must be a string."

    description = raw.get("description", "")
    if not isinstance(description, str):
        return None, f"{tag} ({atom_id}): description must be a string."

    confidence = raw.get("confidence", "medium")
    if not isinstance(confidence, str):
        return None, (
            f"{tag} ({atom_id}): confidence must be a string like 'high' — "
            "normalization of numeric/synonym confidence happens before this "
            "point is reached raw from an analyst."
        )

    source_type = raw.get("source_type")
    if kind in ("fact", "assumption") and not source_type:
        return None, (
            f"{tag} ({atom_id}): a {kind} must state 'source_type' "
            f"(one of {SOURCE_TYPES}) — missing provenance."
        )
    if source_type is not None and source_type not in SOURCE_TYPES:
        return None, f"{tag} ({atom_id}): source_type must be one of {SOURCE_TYPES}."

    value = _as_decimal(raw.get("value"))
    low = _as_decimal(raw.get("low"))
    high = _as_decimal(raw.get("high"))
    formula = raw.get("formula")
    anchor = raw.get("anchor")
    bridge = raw.get("bridge") is True

    if kind == "derived":
        if value is not None:
            # Forgiving, not fatal — mirrors P1: a stray value is ignored, the
            # formula's computed result is what will ever be trusted.
            value = None
        if not isinstance(formula, str) or not formula.strip():
            return None, (
                f"{tag} ({atom_id}): a derived atom needs 'formula' over other "
                "atoms' atom_id — its value is computed downstream, never stated."
            )
        try:
            tree = _parse_formula(formula)
        except _FormulaError as exc:
            return None, f"{tag} ({atom_id}): malformed formula — {exc}"
        if not _formula_ids(tree):
            return None, (
                f"{tag} ({atom_id}): formula {formula!r} references no other "
                "atom — a constant belongs on a fact, not a derived atom."
            )
    elif kind == "unknown":
        # Explicitly "this could not be determined" — distinct from an
        # `assumption` (a reasoned estimate with a plausibility band): an
        # `unknown` atom carries no value, no formula, no band, ever. Never a
        # guess dressed up as a number.
        if value is not None:
            return None, (
                f"{tag} ({atom_id}): an unknown atom must not carry 'value' — "
                "that would make it a guess, not an unknown."
            )
        if formula is not None:
            return None, (
                f"{tag} ({atom_id}): an unknown atom must not carry 'formula' — "
                "nothing computes an unknown value."
            )
        if low is not None or high is not None:
            return None, (
                f"{tag} ({atom_id}): an unknown atom must not carry 'low'/'high' "
                "— a plausibility band belongs to an assumption, not an unknown."
            )
        if not description.strip():
            return None, (
                f"{tag} ({atom_id}): an unknown atom must state 'description' "
                "— what additional analysis or data would resolve it."
            )
    else:
        if formula is not None:
            return None, f"{tag} ({atom_id}): only a derived atom may have 'formula'."
        if value is None or not value.is_finite():
            return None, f"{tag} ({atom_id}): a {kind} needs a finite numeric value."
        if kind == "assumption" and (low is None or high is None):
            return None, (
                f"{tag} ({atom_id}): an assumption must declare a 'low'/'high' "
                "plausibility band."
            )
        if low is not None and high is not None and not (low <= value <= high):
            return None, (
                f"{tag} ({atom_id}): value {value} lies outside its own band "
                f"[{low}, {high}]."
            )

    assumptions = raw.get("assumptions", [])
    if not isinstance(assumptions, list) or not all(
        isinstance(a, str) for a in assumptions
    ):
        return None, f"{tag} ({atom_id}): assumptions must be a list of strings."
    dependencies = raw.get("dependencies", [])
    if not isinstance(dependencies, list) or not all(
        isinstance(d, str) and _SLUG_RE.match(d) for d in dependencies
    ):
        return None, (
            f"{tag} ({atom_id}): dependencies must be a list of atom_id slugs."
        )

    return (
        EvidenceAtom(
            schema_version=SCHEMA_VERSION,
            atom_id=atom_id,
            category=category,
            type=kind,
            title=title,
            unit=unit,
            scope=scope,
            description=description,
            value=value,
            confidence=confidence,
            confidence_reason=str(raw.get("confidence_reason", "")),
            source_type=source_type,
            source_reference=str(raw.get("source_reference", "")),
            assumptions=tuple(assumptions),
            dependencies=tuple(dependencies),
            formula=formula if kind == "derived" else None,
            low=low,
            high=high,
            anchor=anchor if isinstance(anchor, str) else None,
            bridge=bridge,
            created_by=created_by,
            validation_state="unvalidated",
            status="open",
        ),
        None,
    )


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
