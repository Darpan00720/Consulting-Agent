"""Deterministic quantitative verification — the Quant Gate (ADR-009).

Every number a report relies on must be machine-verifiable. The Engagement
Manager's canonical reconciliation ends with a fenced ```quant JSON block (the
**quant ledger**) in which every figure is one of:

* a ``fact``       — a client-stated number, with its provenance;
* an ``assumption`` — with a ``source`` and a plausibility band ``low``/``high``;
* a ``derived``    — with a ``formula`` over other ledger ids, re-evaluated
                     here in exact decimal arithmetic.

This module is pure stdlib and calls no LLM. It is the load-bearing guarantee:
LLM prompts ask for correct math; this code *proves* it or blocks the report.

Checks (ADR-009 §2.2):
  Q1 schema        — required fields per kind, unique ids, valid kinds/values
  Q2 references    — every formula id exists; no self/circular references;
                     formulas reference at least one ledger id; no PCT operand
  Q3 arithmetic    — each formula re-evaluated on the stated input values must
                     equal the stated value within half a unit of its stated
                     precision (state ledger values unrounded; round in prose)
  Q4 units/basis   — additive terms must share unit and basis scope; a derived
                     entry's declared unit must match its formula where known
  Q5 bounds        — assumptions carry source and low <= value <= high
  Q6 anchors       — a derived value anchored to a fact must agree with it
  Q7 bridges       — a ``bridge: true`` entry must be a pure +/- of ledger ids
                     (closure itself is Q3 — the formula must evaluate exactly)

Plus the report tie-out (ADR-009 §2.3): every material number in the final
report (currency, percent, M/B-suffixed, comma-grouped) must match a ledger
value or a figure stated in the client's case prompt.
"""

from __future__ import annotations

import ast
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

KINDS = ("fact", "assumption", "derived")

_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_QUANT_BLOCK_RE = re.compile(r"```quant\s*\n(.*?)```", re.S)

# Upper bound on a `**` exponent in a ledger formula. Decimal's context caps the
# result magnitude anyway; this keeps evaluation cheap and rejects nonsense.
_MAX_EXPONENT = 100


@dataclass(frozen=True)
class QuantDefect:
    """One machine-generated defect. ``message`` is exact and actionable —
    it is fed verbatim back to the Engagement Manager as the rework brief."""

    # schema|reference|arithmetic|units|bounds|anchor|bridge|ledger|tie_out|
    # unknown_evidence
    check: str
    ids: tuple[str, ...]
    message: str


@dataclass(frozen=True)
class Entry:
    id: str
    kind: str
    label: str
    value: Decimal
    unit: str
    scope: str  # basis scope ("annual", "cumulative", ...); "" when undeclared
    formula: str | None
    source: str | None
    low: Decimal | None
    high: Decimal | None
    anchor: str | None
    bridge: bool
    inputs: tuple[str, ...]  # ids parsed out of the formula ("" for non-derived)


@dataclass(frozen=True)
class QuantReport:
    passed: bool
    defects: tuple[QuantDefect, ...]
    # None when no parseable ledger block exists at all.
    entries: Mapping[str, Entry] | None


def _half_ulp(value: Decimal) -> Decimal:
    """Half a unit in the last place of the *stated* precision: a value written
    9.72 tolerates ±0.005; written 9.7200, ±0.00005. This is the only tolerance
    anywhere — the ledger must carry full-precision values (rounding belongs in
    report prose, where the tie-out applies the same rule to the rounded form).
    """
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int):  # NaN/Infinity tuples
        return Decimal(0)
    return Decimal(1).scaleb(exponent) / 2


def _as_decimal(raw: object) -> Decimal | None:
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, Decimal):
        return raw
    if isinstance(raw, int):
        return Decimal(raw)
    return None  # floats never appear: the JSON parser is told to emit Decimal


# --- ledger extraction -------------------------------------------------------


def extract_block(markdown: str) -> str | None:
    """The LAST ```quant block in the text (rework outputs may quote earlier
    versions; the final one is authoritative)."""
    blocks = _QUANT_BLOCK_RE.findall(markdown)
    return blocks[-1] if blocks else None


def _parse_entries(block: str) -> tuple[list[dict[str, Any]], list[QuantDefect]]:
    try:
        data = json.loads(block, parse_float=Decimal, parse_int=Decimal)
    except json.JSONDecodeError as exc:
        return [], [
            QuantDefect(
                "ledger",
                (),
                f"quant ledger is not valid JSON: {exc.msg} at line {exc.lineno}, "
                f"column {exc.colno}. Emit a single JSON array of entry objects.",
            )
        ]
    if isinstance(data, dict):
        data = data.get("entries")
    if not isinstance(data, list) or not data:
        return [], [
            QuantDefect(
                "ledger",
                (),
                "quant ledger must be a non-empty JSON array of entry objects "
                '(or {"entries": [...]}).',
            )
        ]
    bad = [i for i, item in enumerate(data) if not isinstance(item, dict)]
    if bad:
        return [], [
            QuantDefect(
                "ledger",
                (),
                f"quant ledger entries at positions {bad} are not objects.",
            )
        ]
    return data, []


# --- formula handling --------------------------------------------------------

_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)


class _FormulaError(Exception):
    pass


def _parse_formula(formula: str) -> ast.Expression:
    try:
        tree = ast.parse(formula, mode="eval")
    except SyntaxError as exc:
        raise _FormulaError(f"formula does not parse: {exc.msg}") from exc
    for node in ast.walk(tree):
        if isinstance(node, (ast.Expression, ast.Name, ast.Load)):
            continue
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
                raise _FormulaError(f"literal {node.value!r} is not a number")
            continue
        if isinstance(node, ast.BinOp) and isinstance(node.op, _ALLOWED_BINOPS):
            continue
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            continue
        if isinstance(node, (*_ALLOWED_BINOPS, ast.USub, ast.UAdd)):
            continue  # operator nodes themselves
        raise _FormulaError(
            f"disallowed syntax {type(node).__name__} — formulas may use only "
            "+ - * / ** parentheses, numbers, and ledger ids"
        )
    return tree


def _formula_ids(tree: ast.Expression) -> tuple[str, ...]:
    seen: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id not in seen:
            seen.append(node.id)
    return tuple(seen)


def _literal(value: int | float) -> Decimal:
    # ast parses numeric literals to int/float; repr(float) round-trips the
    # shortest decimal form, so `0.05` in a formula becomes Decimal("0.05").
    return Decimal(value) if isinstance(value, int) else Decimal(repr(value))


def _eval(node: ast.AST, values: Mapping[str, Decimal]) -> Decimal:
    if isinstance(node, ast.Expression):
        return _eval(node.body, values)
    if isinstance(node, ast.Constant):
        if not isinstance(node.value, (int, float)) or isinstance(node.value, bool):
            raise _FormulaError(f"literal {node.value!r} is not a number")
        return _literal(node.value)
    if isinstance(node, ast.Name):
        return values[node.id]
    if isinstance(node, ast.UnaryOp):
        operand = _eval(node.operand, values)
        return -operand if isinstance(node.op, ast.USub) else operand
    if isinstance(node, ast.BinOp):
        left, right = _eval(node.left, values), _eval(node.right, values)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            if right == 0:
                raise _FormulaError("division by zero")
            return left / right
        if isinstance(node.op, ast.Pow):
            if right != right.to_integral_value():
                raise _FormulaError(
                    "non-integer exponent — precompute that factor as its own "
                    "derived entry"
                )
            # Bound the exponent explicitly. Decimal's context already caps the
            # result magnitude, but a huge exponent still means a large int and
            # needless work; no real financial formula needs |exponent| > 100.
            if abs(right) > _MAX_EXPONENT:
                raise _FormulaError(
                    f"exponent {right} is out of range (max {_MAX_EXPONENT}) — "
                    "a financial formula should not need a power this large"
                )
            return left ** int(right)
    raise _FormulaError(f"unsupported node {type(node).__name__}")


# Unit/basis signature of a formula subtree: (unit, scope), or None (= unknown,
# e.g. a product — full dimensional analysis is out of scope; additive
# coherence is the check that catches the real-world failures).
def _signature(
    node: ast.AST,
    entries: Mapping[str, Entry],
    defects: list[QuantDefect],
    owner: str,
) -> tuple[str, str] | None:
    if isinstance(node, ast.Expression):
        return _signature(node.body, entries, defects, owner)
    if isinstance(node, ast.Name):
        entry = entries.get(node.id)
        return (entry.unit, entry.scope) if entry else None
    if isinstance(node, ast.UnaryOp):
        return _signature(node.operand, entries, defects, owner)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
        left = _signature(node.left, entries, defects, owner)
        right = _signature(node.right, entries, defects, owner)
        if left is not None and right is not None and left != right:
            op = "+" if isinstance(node.op, ast.Add) else "-"
            defects.append(
                QuantDefect(
                    "units",
                    (owner,),
                    f"{owner}: formula adds ({op}) incompatible terms — "
                    f"{left[0]}/{left[1] or 'no scope'} vs "
                    f"{right[0]}/{right[1] or 'no scope'}. Convert to one unit "
                    "and one basis scope before combining.",
                )
            )
            return None
        return left if left is not None else right
    return None  # Mult/Div/Pow/Constant — unit unknown, no claim made


# --- the verifier ------------------------------------------------------------


def verify_ledger(markdown: str) -> QuantReport:
    """Run checks Q1–Q7 against the ```quant block in ``markdown``.

    Fails closed: a missing or unparseable block is a failure, so the gate
    cannot be skipped by omission.
    """
    block = extract_block(markdown)
    if block is None:
        return QuantReport(
            False,
            (
                QuantDefect(
                    "ledger",
                    (),
                    "no ```quant ledger block found — the canonical "
                    "reconciliation MUST end with one (see the Quant ledger "
                    "section of your instructions).",
                ),
            ),
            None,
        )
    raw_entries, defects = _parse_entries(block)
    if defects:
        return QuantReport(False, tuple(defects), None)

    entries: dict[str, Entry] = {}
    trees: dict[str, ast.Expression] = {}

    # Q1 — schema
    for pos, raw in enumerate(raw_entries):
        eid = raw.get("id")
        if not isinstance(eid, str) or not _ID_RE.match(eid):
            defects.append(
                QuantDefect(
                    "schema",
                    (),
                    f"entry #{pos + 1}: missing or invalid id {eid!r} "
                    "(letters/digits/underscore, starting with a letter).",
                )
            )
            continue
        if eid in entries:
            defects.append(
                QuantDefect(
                    "schema", (eid,), f"{eid}: defined twice — one id, one value."
                )
            )
            continue
        kind = raw.get("kind")
        if kind not in KINDS:
            defects.append(
                QuantDefect(
                    "schema",
                    (eid,),
                    f"{eid}: kind must be one of {KINDS}, got {kind!r}.",
                )
            )
            continue
        value = _as_decimal(raw.get("value"))
        if value is None or not value.is_finite():
            defects.append(
                QuantDefect("schema", (eid,), f"{eid}: value must be a finite number.")
            )
            continue
        unit = raw.get("unit")
        if not isinstance(unit, str) or not unit:
            defects.append(
                QuantDefect(
                    "schema",
                    (eid,),
                    f"{eid}: unit is required (e.g. EUR_M, RATIO, PCT, COUNT).",
                )
            )
            continue
        basis = raw.get("basis")
        scope = ""
        if isinstance(basis, str):
            scope = basis
        elif isinstance(basis, dict):
            scope = str(basis.get("scope") or "")
        label = str(raw.get("label") or eid)
        formula = raw.get("formula")
        source = raw.get("source")
        low, high = _as_decimal(raw.get("low")), _as_decimal(raw.get("high"))
        anchor = raw.get("anchor")
        bridge = raw.get("bridge") is True

        if kind == "derived":
            if not isinstance(formula, str) or not formula.strip():
                defects.append(
                    QuantDefect(
                        "schema",
                        (eid,),
                        f"{eid}: derived entries MUST have a formula over ledger "
                        "ids — a derived number with no formula is a narrated "
                        "number, which this gate exists to forbid.",
                    )
                )
                continue
        else:
            if formula:
                defects.append(
                    QuantDefect(
                        "schema",
                        (eid,),
                        f"{eid}: only derived entries may have a formula — "
                        f"a {kind} is an input, not a computation.",
                    )
                )
                continue
            if not isinstance(source, str) or not source.strip():
                defects.append(
                    QuantDefect(
                        "schema",
                        (eid,),
                        f"{eid}: a {kind} must state its source (client quote, "
                        "benchmark name, or analyst estimate).",
                    )
                )
                continue
            if kind == "assumption" and (low is None or high is None):
                defects.append(
                    QuantDefect(
                        "bounds",
                        (eid,),
                        f"{eid}: assumptions must declare a plausibility band "
                        "low/high — an unbounded assumption cannot be audited.",
                    )
                )
                continue

        inputs: tuple[str, ...] = ()
        if kind == "derived":
            try:
                parsed = _parse_formula(formula)  # type: ignore[arg-type]
                inputs = _formula_ids(parsed)
                trees[eid] = parsed
            except _FormulaError as exc:
                defects.append(QuantDefect("reference", (eid,), f"{eid}: {exc}"))
                continue
            if not inputs:
                defects.append(
                    QuantDefect(
                        "reference",
                        (eid,),
                        f"{eid}: formula {formula!r} references no ledger id — "
                        "a constant formula hides the real inputs.",
                    )
                )
                continue

        entries[eid] = Entry(
            id=eid,
            kind=kind,
            label=label,
            value=value,
            unit=unit,
            scope=scope,
            formula=formula if kind == "derived" else None,
            source=source if isinstance(source, str) else None,
            low=low,
            high=high,
            anchor=anchor if isinstance(anchor, str) else None,
            bridge=bridge,
            inputs=inputs,
        )

    # Q2 — reference integrity (+ no-PCT-operand, cycles)
    for entry in entries.values():
        for ref in entry.inputs:
            target = entries.get(ref)
            if target is None:
                defects.append(
                    QuantDefect(
                        "reference",
                        (entry.id, ref),
                        f"{entry.id}: formula references {ref}, which is not a "
                        "ledger entry.",
                    )
                )
            elif target.unit.upper() == "PCT":
                defects.append(
                    QuantDefect(
                        "reference",
                        (entry.id, ref),
                        f"{entry.id}: formula uses {ref} whose unit is PCT — "
                        "rates used in formulas must be stored as RATIO "
                        "(0.05, not 5) so a 100x error is impossible; keep PCT "
                        "entries display-only.",
                    )
                )
        if entry.id in entry.inputs:
            defects.append(
                QuantDefect(
                    "reference", (entry.id,), f"{entry.id}: formula references itself."
                )
            )

    defects.extend(_cycles(entries))

    # Q3 — arithmetic: re-evaluate every formula on the STATED input values.
    # Stated (not recomputed) inputs localize a defect to the row that is
    # actually wrong instead of cascading it downstream.
    values = {eid: e.value for eid, e in entries.items()}
    for entry in entries.values():
        tree = trees.get(entry.id)
        if tree is None or any(ref not in entries for ref in entry.inputs):
            continue
        try:
            computed = _eval(tree, values)
        except _FormulaError as exc:
            defects.append(QuantDefect("arithmetic", (entry.id,), f"{entry.id}: {exc}"))
            continue
        except (ArithmeticError, OverflowError) as exc:
            defects.append(
                QuantDefect(
                    "arithmetic",
                    (entry.id,),
                    f"{entry.id}: formula evaluation failed ({exc}).",
                )
            )
            continue
        if abs(computed - entry.value) > _half_ulp(entry.value):
            defects.append(
                QuantDefect(
                    "arithmetic",
                    (entry.id,),
                    f"{entry.id} states {entry.value} but formula "
                    f"{entry.formula!r} evaluates to "
                    f"{computed.normalize()} from the stated inputs "
                    f"({', '.join(f'{r}={values[r]}' for r in entry.inputs)}). "
                    "Correct the value or the formula — never round in the "
                    "ledger.",
                )
            )

    # Q4 — unit/basis coherence
    for entry in entries.values():
        tree = trees.get(entry.id)
        if tree is None:
            continue
        sig = _signature(tree, entries, defects, entry.id)
        # Compare UNIT only: a cumulative total is legitimately the sum of
        # annual terms, so the scope of a sum may differ from its operands'.
        if sig is not None and sig[0] != entry.unit:
            defects.append(
                QuantDefect(
                    "units",
                    (entry.id,),
                    f"{entry.id}: declared unit {entry.unit} but its formula "
                    f"combines {sig[0]} terms — declare the unit the formula "
                    "actually produces.",
                )
            )

    # Q5 — assumption bounds
    for entry in entries.values():
        if entry.kind != "assumption":
            continue
        if entry.low is None or entry.high is None:  # rejected by Q1 already
            continue
        if entry.low > entry.high:
            defects.append(
                QuantDefect(
                    "bounds",
                    (entry.id,),
                    f"{entry.id}: low {entry.low} exceeds high {entry.high}.",
                )
            )
        elif not (entry.low <= entry.value <= entry.high):
            defects.append(
                QuantDefect(
                    "bounds",
                    (entry.id,),
                    f"{entry.id}: value {entry.value} lies outside its own "
                    f"plausibility band [{entry.low}, {entry.high}] — either the "
                    "value or the band is wrong; if the value is genuinely "
                    "extraordinary, that is a finding, not an assumption.",
                )
            )

    # Q6 — anchors: an independent fact the derived value must agree with
    for entry in entries.values():
        if not entry.anchor:
            continue
        target = entries.get(entry.anchor)
        if target is None:
            defects.append(
                QuantDefect(
                    "anchor",
                    (entry.id,),
                    f"{entry.id}: anchor {entry.anchor} is not a ledger entry.",
                )
            )
            continue
        if (target.unit, target.scope) != (entry.unit, entry.scope):
            defects.append(
                QuantDefect(
                    "anchor",
                    (entry.id, target.id),
                    f"{entry.id}: anchored to {target.id} but units/basis differ "
                    f"({entry.unit}/{entry.scope or '-'} vs "
                    f"{target.unit}/{target.scope or '-'}).",
                )
            )
            continue
        tolerance = _half_ulp(entry.value) + _half_ulp(target.value)
        if abs(entry.value - target.value) > tolerance:
            defects.append(
                QuantDefect(
                    "anchor",
                    (entry.id, target.id),
                    f"{entry.id} ({entry.value}) contradicts its independent "
                    f"anchor {target.id} ({target.value}) — the analysis is "
                    "internally inconsistent; reconcile before anything "
                    "downstream cites either number.",
                )
            )

    # Q7 — bridges must be pure sums of ledger ids (closure is Q3)
    for entry in entries.values():
        if not entry.bridge:
            continue
        tree = trees.get(entry.id)
        if tree is None:
            defects.append(
                QuantDefect(
                    "bridge",
                    (entry.id,),
                    f"{entry.id}: bridge entries must be derived, with a formula.",
                )
            )
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp) and not isinstance(
                node.op, (ast.Add, ast.Sub)
            ):
                defects.append(
                    QuantDefect(
                        "bridge",
                        (entry.id,),
                        f"{entry.id}: a bridge is a pure sum of named components "
                        "(+/- of ledger ids only) — factor any product into its "
                        "own derived entry, so the bridge closes term by term.",
                    )
                )
                break
            if isinstance(node, ast.Constant):
                defects.append(
                    QuantDefect(
                        "bridge",
                        (entry.id,),
                        f"{entry.id}: bridge contains a bare literal "
                        f"{node.value!r} — every bridge component must be a "
                        "named ledger entry (that is the point of a bridge).",
                    )
                )
                break

    return QuantReport(not defects, tuple(defects), entries)


def _cycles(entries: Mapping[str, Entry]) -> list[QuantDefect]:
    """DFS cycle detection over the formula dependency graph."""
    WHITE, GREY, BLACK = 0, 1, 2
    color = dict.fromkeys(entries, WHITE)
    defects: list[QuantDefect] = []

    def visit(eid: str, path: list[str]) -> None:
        color[eid] = GREY
        path.append(eid)
        for ref in entries[eid].inputs:
            if ref not in entries:
                continue
            if color[ref] == GREY:
                cycle = path[path.index(ref) :] + [ref]
                defects.append(
                    QuantDefect(
                        "reference",
                        tuple(cycle[:-1]),
                        "circular derivation: "
                        + " -> ".join(cycle)
                        + " — a value may never be derived from itself "
                        "(no back-solved valuations).",
                    )
                )
            elif color[ref] == WHITE:
                visit(ref, path)
        path.pop()
        color[eid] = BLACK

    for eid in entries:
        if color[eid] == WHITE:
            visit(eid, [])
    return defects


# --- report tie-out (ADR-009 §2.3) -------------------------------------------

# Material numbers in a report: currency, percents, magnitude-suffixed, and
# comma-grouped figures. Deliberately NOT every integer — "3 options" or
# "Step 2" is prose structure, not a quantitative claim.
#
# The leading sign group is deliberately narrow: a `-`/`−`/`–`
# (ASCII hyphen, Unicode minus, en-dash — all three appear in LLM-written
# prose for a negative figure, e.g. "ROIC dropped ... to –4%") counts as a
# sign ONLY when it is not itself preceded by a digit. That distinguishes a
# genuine negative ("deliver –4% ROIC") from a range's separator
# ("62-75%" utilization) — the hyphen in a range is always digit-adjacent on
# its left, a sign prefix never is. Real bug, found by reproducing a live
# report where a correctly-cited negative ledger value (ROIC = -4%) was
# flagged as an "orphan number": the old pattern had no sign group at all, so
# "-4%" and "4%" parsed to the identical positive Decimal, and a negative
# ledger entry could never tie out against its own correct citation.
_NUMBER_TOKEN = re.compile(
    r"""
    (?P<sign>(?<!\d)[-−–])?\s*
    (?P<curr>[€$£])?\s*
    (?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)
    \s*(?P<suffix>%|pp\b|[MBk]\b|million\b|billion\b|bn\b)?
    """,
    re.X,
)
_YEAR = re.compile(r"^(19|20)\d{2}$")


def _report_numbers(text: str) -> list[tuple[Decimal, str, str]]:
    """(value, suffix, context-snippet) for every MATERIAL number in the text."""
    found: list[tuple[Decimal, str, str]] = []
    for match in _NUMBER_TOKEN.finditer(text):
        raw, suffix, curr = match["num"], match["suffix"] or "", match["curr"] or ""
        if not (curr or suffix or "," in raw):
            continue  # bare small number — prose structure, not a claim
        plain = raw.replace(",", "")
        if _YEAR.match(plain) and not curr and suffix in ("", "k"):
            continue  # calendar years ("2026", "FY-2029")
        if (
            text[max(0, match.start() - 3) : match.start()]
            .upper()
            .endswith(("FY-", "FY"))
        ):
            continue
        try:
            value = Decimal(plain)
        except InvalidOperation:  # pragma: no cover - regex guarantees digits
            continue
        if match["sign"]:
            value = -value
        lo = max(0, match.start() - 40)
        snippet = " ".join(text[lo : match.end() + 20].split())
        found.append((value, suffix, snippet))
    return found


def _scale_variants(value: Decimal, unit: str) -> list[Decimal]:
    """A ledger value plus the display scales a report may legitimately use."""
    upper = unit.upper()
    variants = [value]
    if upper == "RATIO":
        variants.append(value * 100)  # 0.30 shown as 30%
    elif upper == "PCT":
        variants.append(value / 100)
    elif upper.endswith("_M"):
        variants.append(value / 1000)  # €2,680M shown as €2.68B
    elif upper.endswith("_B"):
        variants.append(value * 1000)
    return variants


def tie_out(
    report_md: str,
    entries: Mapping[str, Entry] | None,
    case_prompt: str,
) -> QuantReport:
    """No orphan numbers: every material figure in the report must match a
    ledger value or a number stated in the client's own case prompt, within
    half a unit of the precision the report displays it at."""
    candidates: list[Decimal] = []
    if entries:
        for entry in entries.values():
            candidates.extend(_scale_variants(entry.value, entry.unit))
            for bound in (entry.low, entry.high):
                if bound is not None:
                    candidates.extend(_scale_variants(bound, entry.unit))
    for value, suffix, _ in _report_numbers(case_prompt):
        candidates.append(value)
        if suffix in ("B", "billion", "bn"):
            candidates.append(value * 1000)  # case "€3.2B" quoted as €3,200M

    defects: list[QuantDefect] = []
    seen: set[tuple[Decimal, str]] = set()
    for value, suffix, snippet in _report_numbers(report_md):
        if (value, suffix) in seen:
            continue
        seen.add((value, suffix))
        forms = [value]
        if suffix in ("B", "billion", "bn"):
            forms.append(value * 1000)
        tolerance = _half_ulp(value)
        if any(abs(c - form) <= tolerance for c in candidates for form in forms):
            continue
        defects.append(
            QuantDefect(
                "tie_out",
                (),
                f'orphan number {value}{suffix and " " + suffix} in: "{snippet}" '
                "— matches no quant-ledger value and no figure in the client's "
                "case prompt. Every figure must be a ledger value (rounded for "
                "prose is fine) — never re-derive or invent a number in the "
                "report.",
            )
        )
    return QuantReport(not defects, tuple(defects), entries)


def format_defects(report: QuantReport) -> str:
    """The defect list as a deterministic rework brief."""
    lines = [f"{i}. [{d.check}] {d.message}" for i, d in enumerate(report.defects, 1)]
    return "\n".join(lines)


# --- unresolved unknowns (Recommendation Gate backstop) ----------------------

_EVIDENCE_INSUFFICIENT = "evidence insufficient"


def unresolved_unknowns(report_md: str, unknown_labels: tuple[str, ...]) -> QuantReport:
    """Backstop for the Recommendation Gate: an ``unknown`` atom (a metric the
    Engagement Manager explicitly declared could not be determined — no
    reasonable estimate exists) must not be silently dropped or treated as
    settled once the report is written.

    Deliberately coarse, not a full dependency trace: nothing in this
    pipeline reliably maps a free-text report claim back to the specific
    atom it depends on, so this does not attempt to prove a *recommendation*
    rests on an unknown. It proves something narrower but still real: for
    each unknown label whose text is discussed anywhere in the report, an
    explicit "Evidence Insufficient" marker (case-insensitive) must appear
    nearby. A label never mentioned in the report at all is not flagged —
    the report made no claim about it, so there is nothing to gate.
    """
    defects: list[QuantDefect] = []
    lower_report = report_md.lower()
    for label in unknown_labels:
        needle = label.strip().lower()
        if not needle:
            continue
        pos = lower_report.find(needle)
        if pos == -1:
            continue  # never discussed — nothing to gate
        window = report_md[max(0, pos - 250) : pos + len(label) + 250].lower()
        if _EVIDENCE_INSUFFICIENT not in window:
            defects.append(
                QuantDefect(
                    "unknown_evidence",
                    (),
                    f"the Engagement Manager declared {label!r} UNKNOWN (no "
                    "reasonable estimate exists), but the report discusses it "
                    "without framing it as 'Evidence Insufficient' nearby — "
                    "an unknown may not be silently treated as resolved. "
                    "Either add that framing next to this discussion or "
                    "remove the claim.",
                )
            )
    return QuantReport(not defects, tuple(defects), None)


# --- Decimal-safe JSON (shared by ledger_builder.py and evidence_store.py) --

# Wrap each Decimal in a sentinel so json.dumps emits it as a quoted string,
# then strip the quotes so the ledger carries a bare NUMBER — verify_ledger
# re-parses with parse_float=Decimal and rejects a stringified value. The
# token is printable ASCII (json does not escape it, unlike a NUL byte) and
# the unquote only fires on sentinel-wrapped NUMERIC content, so it can never
# mangle a label. default() is invoked only for Decimal objects, so nothing
# but a real value is ever wrapped. Extracted here (rather than duplicated in
# both ADR-010 modules that build ledger-shaped JSON) because this is the
# lowest-level module both already depend on for the Decimal-exact contract.
_DEC_SENTINEL = "@@DEC@@"
_DEC_UNQUOTE = re.compile(
    '"' + _DEC_SENTINEL + r"(-?[0-9][0-9.eE+\-]*)" + _DEC_SENTINEL + '"'
)


def dump_decimal_json(rows: list[dict[str, object]]) -> str:
    """``json.dumps`` that preserves ``Decimal`` values as bare JSON numbers."""

    def _default(o: object) -> object:
        if isinstance(o, Decimal):
            return f"{_DEC_SENTINEL}{o}{_DEC_SENTINEL}"
        raise TypeError(f"not serializable: {type(o).__name__}")

    text = json.dumps(rows, indent=1, default=_default)
    return _DEC_UNQUOTE.sub(lambda m: m.group(1), text)
