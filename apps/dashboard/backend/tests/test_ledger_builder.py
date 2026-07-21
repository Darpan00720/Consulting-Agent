"""Deterministic Ledger Builder tests (ADR-010 Phase 1).

The builder is the fix for the 7/7 live Quant-Gate failures: the LLM emits
evidence ATOMS and code assembles the ledger — minting ids, translating
key-references into id-formulas, and COMPUTING every derived value itself. These
tests pin that contract:

* atoms → a ledger that PASSES the existing verifier (round-trip);
* the LLM cannot inject a wrong calculation (derived values are recomputed);
* structural failures that used to sink real runs (dangling refs, id collisions,
  cycles, malformed JSON) are caught deterministically with actionable messages;
* backward compatibility — a reconciliation with no atoms block is untouched;
* integration — an EM that emits atoms drives a clean, review-ready engagement.
"""

from __future__ import annotations

import asyncio
import json
import os

os.environ.setdefault("STRATAGENT_MOCK", "1")

from app import config, db
from app.pipeline import ledger_builder as lb
from app.pipeline import quantcheck as qc
from app.pipeline.engine import run_engagement

from .test_api import CASE, fake_output


def _atoms(*objects: str) -> str:
    return "reconciliation prose\n\n```atoms\n[" + ",".join(objects) + "]\n```\n"


REVENUE = (
    '{"key":"revenue","kind":"fact","label":"Revenue FY26","value":324,'
    '"unit":"EUR_M","scope":"annual","source":"client_fact"}'
)
SHARE = (
    '{"key":"delivery_share","kind":"assumption","label":"Delivery share",'
    '"value":0.20,"unit":"RATIO","scope":"annual","source":"analyst_estimate",'
    '"low":0.10,"high":0.25}'
)
COMMISSION = (
    '{"key":"commission","kind":"assumption","label":"Commission","value":0.30,'
    '"unit":"RATIO","scope":"annual","source":"benchmark","low":0.20,"high":0.35}'
)
DRAIN = (
    '{"key":"drain","kind":"derived","label":"Delivery commission drain",'
    '"unit":"EUR_M","scope":"annual",'
    '"expr":"revenue * delivery_share * commission"}'
)


def _entries(markdown: str) -> dict[str, dict]:
    return {e["id"]: e for e in json.loads(qc.extract_block(markdown))}


# --- round-trip: atoms build a ledger the verifier accepts --------------------


def test_atoms_build_a_passing_ledger():
    result = lb.build_from_markdown(_atoms(REVENUE, SHARE, COMMISSION, DRAIN))
    assert result.had_atoms and result.errors == ()
    report = qc.verify_ledger(result.markdown)
    assert report.passed, [d.message for d in report.defects]


UNKNOWN = (
    '{"key":"factory_util","kind":"unknown","label":"Factory utilization by '
    'plant","unit":"RATIO","source":"needs plant-level OEE reports"}'
)


def test_unknown_atom_is_excluded_from_the_ledger_not_given_an_id():
    """An `unknown` atom carries no value — it must never become an A-n/D-n
    ledger entry (that would silently turn 'we don't know' into a number)."""
    result = lb.build_from_markdown(_atoms(REVENUE, UNKNOWN))
    assert result.had_atoms and result.errors == ()
    assert result.unknowns == ("Factory utilization by plant",)
    entries = _entries(result.markdown)
    assert list(entries) == ["A1"]  # only REVENUE got an id; UNKNOWN did not
    assert qc.verify_ledger(result.markdown).passed


def test_unknown_atom_with_a_value_is_rejected():
    guessing = UNKNOWN[:-1] + ',"value":0.62}'
    result = lb.build_from_markdown(_atoms(REVENUE, guessing))
    assert result.errors and "must not carry a 'value'" in result.errors[0]


def test_unknown_atom_with_an_expr_is_rejected():
    computing = UNKNOWN[:-1] + ',"expr":"revenue * 2"}'
    result = lb.build_from_markdown(_atoms(REVENUE, computing))
    assert result.errors and "must not carry an 'expr'" in result.errors[0]


def test_unknown_atom_with_a_band_is_rejected():
    banded = UNKNOWN[:-1] + ',"low":0.5,"high":0.7}'
    result = lb.build_from_markdown(_atoms(REVENUE, banded))
    assert result.errors and "must not carry 'low'/'high'" in result.errors[0]


def test_unknown_atom_without_source_is_rejected():
    no_source = UNKNOWN.replace(',"source":"needs plant-level OEE reports"', "")
    result = lb.build_from_markdown(_atoms(REVENUE, no_source))
    assert result.errors and "must state 'source'" in result.errors[0]


def test_derived_atom_cannot_reference_an_unknown_atoms_key():
    """An unknown atom's key is never minted an id, so any derived atom
    referencing it fails the existing dangling-reference check — for free."""
    references_unknown = (
        '{"key":"shortfall","kind":"derived","label":"Shortfall",'
        '"unit":"EUR_M","expr":"revenue - factory_util"}'
    )
    result = lb.build_from_markdown(_atoms(REVENUE, UNKNOWN, references_unknown))
    assert result.errors and "unknown atom key" in result.errors[0]


def test_keys_are_translated_to_canonical_ids():
    result = lb.build_from_markdown(_atoms(REVENUE, SHARE, COMMISSION, DRAIN))
    entries = _entries(result.markdown)
    # facts/assumptions → A-n, derived → D-n, in declared order.
    assert entries["A1"]["label"] == "Revenue FY26"
    assert entries["D1"]["formula"] == "A1 * A2 * A3"  # keys resolved to ids
    # values are bare JSON numbers, not strings
    assert isinstance(entries["A1"]["value"], int)


# --- assumption criticality (Issue 3, 2026-07-21) ----------------------------


def test_assumption_criticality_defaults_to_material_when_omitted():
    """SHARE never declares 'criticality' -- 2026-07-21 backward-compat
    default applies so pre-existing atoms (and every test fixture written
    before this feature) never silently become the least-consequential kind."""
    result = lb.build_from_markdown(_atoms(REVENUE, SHARE, COMMISSION, DRAIN))
    entries = _entries(result.markdown)
    assert entries["A2"]["criticality"] == "material"
    assert entries["A3"]["criticality"] == "material"
    assert "criticality" not in entries["A1"]  # a fact never carries it


def test_assumption_criticality_explicit_value_is_preserved():
    load_bearing = SHARE[:-1] + ',"criticality":"load_bearing"}'
    result = lb.build_from_markdown(_atoms(REVENUE, load_bearing, COMMISSION, DRAIN))
    entries = _entries(result.markdown)
    assert entries["A2"]["criticality"] == "load_bearing"


def test_assumption_criticality_rejects_an_invalid_value():
    bad = SHARE[:-1] + ',"criticality":"vital"}'
    result = lb.build_from_markdown(_atoms(REVENUE, bad, COMMISSION, DRAIN))
    assert result.errors and "must be one of" in result.errors[0]


def test_fact_cannot_carry_criticality():
    fact_with_criticality = REVENUE[:-1] + ',"criticality":"supporting"}'
    result = lb.build_from_markdown(
        _atoms(fact_with_criticality, SHARE, COMMISSION, DRAIN)
    )
    assert (
        result.errors
        and "only an assumption may carry 'criticality'" in result.errors[0]
    )


def test_derived_value_is_computed_not_trusted():
    """The whole point: the LLM cannot inject a wrong calculation. Even if a
    derived atom carries a bogus value, the builder recomputes it and the gate
    still passes on the CORRECT figure."""
    lying = DRAIN[:-1] + ',"value":999}'  # 324*0.20*0.30 = 19.44, not 999
    result = lb.build_from_markdown(_atoms(REVENUE, SHARE, COMMISSION, lying))
    entries = _entries(result.markdown)
    assert entries["D1"]["value"] in (19.44, "19.44") or str(
        entries["D1"]["value"]
    ).startswith("19.44")
    assert qc.verify_ledger(result.markdown).passed


def test_multi_level_derived_chain_computes_in_order():
    then = (
        '{"key":"ebitda_then","kind":"fact","label":"EBITDA FY23","value":51.3,'
        '"unit":"EUR_M","scope":"annual","source":"client_fact"}'
    )
    now = (
        '{"key":"ebitda_now","kind":"fact","label":"EBITDA FY26","value":35.64,'
        '"unit":"EUR_M","scope":"annual","source":"client_fact"}'
    )
    decline = (
        '{"key":"decline","kind":"derived","label":"Decline","unit":"EUR_M",'
        '"scope":"annual","expr":"ebitda_then - ebitda_now"}'
    )
    pct = (
        '{"key":"pct","kind":"derived","label":"Decline pct","unit":"RATIO",'
        '"scope":"annual","expr":"decline / ebitda_then"}'
    )
    result = lb.build_from_markdown(_atoms(then, now, decline, pct))
    assert result.errors == ()
    entries = _entries(result.markdown)
    # decline = 15.66; pct depends on decline (declared before it) → topo order
    assert str(entries["D1"]["value"]).startswith("15.66")
    assert qc.verify_ledger(result.markdown).passed


# --- structural failures caught deterministically -----------------------------


def test_dangling_key_reference_is_an_error():
    bad = (
        '{"key":"d","kind":"derived","label":"x","unit":"EUR_M",'
        '"expr":"revenue * nonexistent"}'
    )
    result = lb.build_from_markdown(_atoms(REVENUE, bad))
    assert any("unknown atom key" in e for e in result.errors)


def test_stray_value_on_a_derived_atom_is_ignored_not_trusted():
    """Deliberately forgiving: if the LLM mistakenly puts a value on a derived
    atom, the builder ignores it and computes the real one — robustness over
    strictness, and the computed figure is authoritative regardless."""
    stray = (
        '{"key":"drain","kind":"derived","label":"x","unit":"EUR_M",'
        '"scope":"annual","value":999,'
        '"expr":"revenue * delivery_share * commission"}'
    )
    result = lb.build_from_markdown(_atoms(REVENUE, SHARE, COMMISSION, stray))
    assert result.errors == ()  # not rejected — forgiven
    assert str(_entries(result.markdown)["D1"]["value"]).startswith("19.44")
    assert qc.verify_ledger(result.markdown).passed


def test_assumption_without_band_is_an_error():
    bad = (
        '{"key":"a","kind":"assumption","label":"x","value":0.2,"unit":"RATIO",'
        '"source":"guess"}'
    )
    result = lb.build_from_markdown(_atoms(bad))
    assert any("band" in e for e in result.errors)


def test_fact_without_source_is_an_error():
    bad = '{"key":"a","kind":"fact","label":"x","value":1,"unit":"EUR_M"}'
    result = lb.build_from_markdown(_atoms(bad))
    assert any("source" in e for e in result.errors)


def test_conflicting_duplicate_key_is_an_error():
    a = REVENUE
    b = REVENUE.replace('"value":324', '"value":999')
    result = lb.build_from_markdown(_atoms(a, b))
    assert any("declared twice" in e for e in result.errors)


def test_identical_duplicate_key_collapses():
    result = lb.build_from_markdown(_atoms(REVENUE, REVENUE))
    assert result.errors == ()
    assert len(_entries(result.markdown)) == 1


def test_duplicate_key_with_different_band_is_a_conflict_not_silently_dropped():
    """Regression for a real bug an external Codex review found (2026-07-17):
    two atoms with the same key/value but a DIFFERENT low/high band were
    treated as identical, so the second (possibly tighter, more correct) band
    was silently discarded instead of being flagged as a conflict."""
    wide = (
        '{"key":"share","kind":"assumption","label":"Share","value":0.2,'
        '"unit":"RATIO","source":"s","low":0.1,"high":0.3}'
    )
    tight = wide.replace('"low":0.1,"high":0.3', '"low":0.19,"high":0.21')
    result = lb.build_from_markdown(_atoms(wide, tight))
    assert any("declared twice" in e for e in result.errors)


def test_last_atoms_block_wins_over_a_quoted_stale_one():
    """Regression for a real bug an external Codex review found and a
    reproduction confirmed (2026-07-17): engine.py's rework prompt quotes
    "Your previous canonical reconciliation" (including its stale ```atoms
    block) BEFORE asking for the correction. A first-match extraction was
    silently rebuilding the ledger from the OLD, pre-correction values on
    every rework — the exact scenario this test reproduces directly."""
    stale = REVENUE.replace('"value":324', '"value":100')
    corrected = REVENUE  # value:324
    md = (
        "Your previous canonical reconciliation:\n"
        + _atoms(stale)
        + "\n\nCorrected:\n"
        + _atoms(corrected)
    )
    result = lb.build_from_markdown(md)
    assert result.errors == ()
    entries = _entries(result.markdown)
    assert entries["A1"]["value"] == 324


def test_cycle_is_detected():
    a = '{"key":"a","kind":"derived","label":"a","unit":"X","expr":"b + 1"}'
    b = '{"key":"b","kind":"derived","label":"b","unit":"X","expr":"a + 1"}'
    result = lb.build_from_markdown(_atoms(a, b))
    assert any("circular derivation" in e for e in result.errors)


def test_malformed_json_is_an_error():
    result = lb.build_from_markdown("```atoms\n[{oops}]\n```")
    assert any("not valid JSON" in e for e in result.errors)


def test_disallowed_expr_syntax_is_rejected():
    bad = (
        '{"key":"d","kind":"derived","label":"x","unit":"EUR_M",'
        '"expr":"__import__(\'os\')"}'
    )
    result = lb.build_from_markdown(_atoms(REVENUE, bad))
    assert result.errors


# --- backward compatibility ---------------------------------------------------


def test_no_atoms_block_passes_through_untouched():
    plain = "canonical reconciliation with a ```quant\n[]\n``` and no atoms"
    result = lb.build_from_markdown(plain)
    assert result.had_atoms is False
    assert result.errors == ()
    assert result.markdown == plain


# --- integration: EM emits atoms → clean engagement ---------------------------


def _drain(coro):
    asyncio.run(coro)


def test_engagement_manager_atoms_drive_a_review_ready_run(tmp_path, monkeypatch):
    """An EM that emits evidence atoms (not a hand-authored ledger) produces a
    ledger the gate accepts and a review-ready engagement — the P1 happy path."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "atoms_ok.db")
    db.reset_for_tests()

    em_atoms = "## Canonical reconciliation\n\n" + _atoms(
        REVENUE, SHARE, COMMISSION, DRAIN
    )

    async def fake_call(agent, system, user, **kw):
        if agent == "engagement-manager":
            return em_atoms
        return fake_output(agent)

    eid = db.create_engagement("browser-x", CASE)
    _drain(run_engagement(eid, CASE, call=fake_call))

    completed = next(
        e for e in db.list_events(eid) if e["type"] == "engagement_completed"
    )
    assert completed["payload"]["review_ready"] is True
    gate = [e for e in db.list_events(eid) if e["type"] == "quant_gate"]
    assert gate[-1]["payload"]["passed"] is True
    db.reset_for_tests()


def test_malformed_atoms_trigger_rework_then_recover(tmp_path, monkeypatch):
    """Malformed atoms surface as a gate defect and drive the same EM rework
    loop as a verifier failure; a corrected atom set then passes."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "atoms_rework.db")
    monkeypatch.setattr(config, "MAX_REWORK", 1)
    db.reset_for_tests()
    em_calls = {"n": 0}
    briefs: list[str] = []

    good = "## Reconciliation\n\n" + _atoms(REVENUE, SHARE, COMMISSION, DRAIN)
    # first attempt references a key that doesn't exist → builder error
    broken_drain = (
        '{"key":"drain","kind":"derived","label":"x","unit":"EUR_M",'
        '"expr":"revenue * missing_key"}'
    )
    broken = "## Reconciliation\n\n" + _atoms(REVENUE, SHARE, COMMISSION, broken_drain)

    async def fake_call(agent, system, user, **kw):
        if agent == "engagement-manager":
            em_calls["n"] += 1
            if "QUANT GATE DEFECTS" in user:
                briefs.append(user)
                return good
            return broken
        return fake_output(agent)

    eid = db.create_engagement("browser-x", CASE)
    _drain(run_engagement(eid, CASE, call=fake_call))

    assert em_calls["n"] == 2  # initial + one deterministic fix
    assert briefs and "unknown atom key" in briefs[0]
    completed = next(
        e for e in db.list_events(eid) if e["type"] == "engagement_completed"
    )
    assert completed["payload"]["review_ready"] is True
    db.reset_for_tests()
