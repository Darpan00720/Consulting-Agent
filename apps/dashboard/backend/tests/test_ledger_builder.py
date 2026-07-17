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


def test_keys_are_translated_to_canonical_ids():
    result = lb.build_from_markdown(_atoms(REVENUE, SHARE, COMMISSION, DRAIN))
    entries = _entries(result.markdown)
    # facts/assumptions → A-n, derived → D-n, in declared order.
    assert entries["A1"]["label"] == "Revenue FY26"
    assert entries["D1"]["formula"] == "A1 * A2 * A3"  # keys resolved to ids
    # values are bare JSON numbers, not strings
    assert isinstance(entries["A1"]["value"], int)


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
