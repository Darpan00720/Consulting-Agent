"""Quant Gate tests (ADR-009).

Three layers:
* unit tests per verifier check (Q1–Q7) and for the report tie-out;
* the EspressoLux regression — a ledger + report encoding the seven defect
  classes (F-1..F-7) that shipped in the 2026-07-16 engagement with
  reviewer=approved; every one must now fail deterministically;
* pipeline integration — a planted arithmetic error triggers a deterministic
  Engagement-Manager rework with the exact defect, and an orphan number in the
  report triggers a report rework; unresolved failures fail closed
  (review_ready=False), never ship as a confident final report.
"""

from __future__ import annotations

import asyncio
import os

os.environ.setdefault("STRATAGENT_MOCK", "1")

from app import config, db
from app.pipeline import quantcheck
from app.pipeline.engine import run_engagement

from .test_api import CASE, QUANT, fake_output


def _ledger(entries_json: str) -> str:
    return f"reconciliation text\n\n```quant\n[{entries_json}]\n```\n"


FACT = (
    '{"id":"F1","kind":"fact","label":"Revenue","value":324,'
    '"unit":"EUR_M","basis":"annual","source":"case: revenue €324M"}'
)
ASSUMPTION = (
    '{"id":"A1","kind":"assumption","label":"Delivery share","value":0.20,'
    '"unit":"RATIO","basis":"annual","source":"POS split","low":0.10,"high":0.25}'
)


def defect_checks(report: quantcheck.QuantReport) -> set[str]:
    return {d.check for d in report.defects}


# --- extraction & schema (Q1) -------------------------------------------------


def test_missing_block_fails_closed():
    report = quantcheck.verify_ledger("no ledger anywhere")
    assert not report.passed
    assert report.entries is None
    assert defect_checks(report) == {"ledger"}


def test_invalid_json_fails_with_position():
    report = quantcheck.verify_ledger("```quant\n[{oops}]\n```")
    assert not report.passed
    assert "not valid JSON" in report.defects[0].message


def test_last_block_wins():
    text = _ledger('{"id":"F1","kind":"fact"}') + _ledger(FACT)
    assert quantcheck.verify_ledger(text).passed


def test_duplicate_id_rejected():
    report = quantcheck.verify_ledger(_ledger(f"{FACT},{FACT}"))
    assert any("defined twice" in d.message for d in report.defects)


def test_derived_without_formula_is_a_narrated_number():
    entry = (
        '{"id":"D1","kind":"derived","label":"Unexplained OPEX","value":50.19,'
        '"unit":"EUR_M","basis":"annual"}'
    )
    report = quantcheck.verify_ledger(_ledger(entry))
    assert any("narrated number" in d.message for d in report.defects)


def test_fact_requires_source_and_no_formula():
    no_source = '{"id":"F1","kind":"fact","label":"x","value":1,"unit":"EUR_M"}'
    report = quantcheck.verify_ledger(_ledger(no_source))
    assert any("source" in d.message for d in report.defects)

    with_formula = (
        '{"id":"F1","kind":"fact","label":"x","value":1,"unit":"EUR_M",'
        '"source":"case","formula":"F1*2"}'
    )
    report = quantcheck.verify_ledger(_ledger(with_formula))
    assert any(
        "only derived entries may have a formula" in d.message for d in report.defects
    )


# --- references (Q2) -----------------------------------------------------------


def test_unknown_reference_and_cycle():
    dangling = (
        f'{FACT},{{"id":"D1","kind":"derived","label":"x","value":1,'
        f'"unit":"EUR_M","formula":"F1 * NOPE"}}'
    )
    report = quantcheck.verify_ledger(_ledger(dangling))
    assert any("NOPE" in d.message for d in report.defects)

    circular = (
        '{"id":"D1","kind":"derived","label":"a","value":1,"unit":"EUR_M",'
        '"formula":"D2 + 0"},'
        '{"id":"D2","kind":"derived","label":"b","value":1,"unit":"EUR_M",'
        '"formula":"D1 + 0"}'
    )
    report = quantcheck.verify_ledger(_ledger(circular))
    assert any("circular derivation" in d.message for d in report.defects)


def test_pct_operand_forbidden_in_formulas():
    pct = (
        '{"id":"P1","kind":"assumption","label":"rate","value":30,"unit":"PCT",'
        '"source":"benchmark","low":20,"high":35},'
        f"{FACT},"
        '{"id":"D1","kind":"derived","label":"drain","value":97.2,'
        '"unit":"EUR_M","formula":"F1 * P1"}'
    )
    report = quantcheck.verify_ledger(_ledger(pct))
    assert any("RATIO" in d.message and "100x" in d.message for d in report.defects)


def test_constant_only_formula_rejected():
    entry = (
        '{"id":"D1","kind":"derived","label":"x","value":19.44,'
        '"unit":"EUR_M","formula":"19.44"}'
    )
    report = quantcheck.verify_ledger(_ledger(entry))
    assert any("references no ledger id" in d.message for d in report.defects)


def test_disallowed_syntax_rejected():
    entry = (
        '{"id":"D1","kind":"derived","label":"x","value":1,'
        '"unit":"EUR_M","formula":"__import__(\'os\').system(\'true\')"}'
    )
    report = quantcheck.verify_ledger(_ledger(entry))
    assert any("disallowed syntax" in d.message for d in report.defects)


# --- arithmetic (Q3) ------------------------------------------------------------


def test_arithmetic_mismatch_reports_expected_value():
    bad = (
        f"{FACT},{ASSUMPTION},"
        '{"id":"A2","kind":"assumption","label":"commission","value":0.30,'
        '"unit":"RATIO","basis":"annual","source":"rate card","low":0.20,"high":0.35},'
        '{"id":"D1","kind":"derived","label":"drain","value":21.06,'
        '"unit":"EUR_M","basis":"annual","formula":"F1 * A1 * A2"}'
    )
    report = quantcheck.verify_ledger(_ledger(bad))
    [defect] = [d for d in report.defects if d.check == "arithmetic"]
    assert "21.06" in defect.message and "19.44" in defect.message


def test_stated_precision_is_the_tolerance():
    # 324 * 0.11 = 35.64 — stating 35.6 (one decimal) is within half an ulp,
    # stating 35.7 is not.
    base = (
        f"{FACT},"
        '{"id":"M1","kind":"fact","label":"margin","value":0.11,"unit":"RATIO",'
        '"basis":"annual","source":"case"},'
    )
    ok = base + (
        '{"id":"D1","kind":"derived","label":"EBITDA","value":35.6,'
        '"unit":"EUR_M","basis":"annual","formula":"F1 * M1"}'
    )
    assert quantcheck.verify_ledger(_ledger(ok)).passed
    off = ok.replace('"value":35.6', '"value":35.7')
    assert not quantcheck.verify_ledger(_ledger(off)).passed


def test_division_by_zero_and_bad_exponent():
    zero = (
        f'{FACT},{{"id":"Z","kind":"fact","label":"z","value":0,"unit":"COUNT",'
        f'"source":"case"}},'
        '{"id":"D1","kind":"derived","label":"x","value":1,"unit":"EUR_M",'
        '"formula":"F1 / Z"}'
    )
    report = quantcheck.verify_ledger(_ledger(zero))
    assert any("division by zero" in d.message for d in report.defects)

    frac = (
        f"{FACT},"
        '{"id":"D1","kind":"derived","label":"x","value":18,'
        '"unit":"EUR_M","formula":"F1 ** 0.5"}'
    )
    report = quantcheck.verify_ledger(_ledger(frac))
    assert any("non-integer exponent" in d.message for d in report.defects)


# --- units & basis (Q4) ----------------------------------------------------------


def test_adding_mixed_units_or_scopes_fails():
    mixed_units = (
        f"{FACT},{ASSUMPTION},"
        '{"id":"D1","kind":"derived","label":"x","value":324.2,'
        '"unit":"EUR_M","basis":"annual","formula":"F1 + A1"}'
    )
    report = quantcheck.verify_ledger(_ledger(mixed_units))
    assert any(d.check == "units" for d in report.defects)

    mixed_scope = (
        f"{FACT},"
        '{"id":"C1","kind":"fact","label":"3yr total","value":900,'
        '"unit":"EUR_M","basis":"cumulative_3yr","source":"case"},'
        '{"id":"D1","kind":"derived","label":"x","value":1224,'
        '"unit":"EUR_M","basis":"annual","formula":"F1 + C1"}'
    )
    report = quantcheck.verify_ledger(_ledger(mixed_scope))
    assert any("scope" in d.message for d in report.defects if d.check == "units")


def test_cumulative_total_of_annual_terms_is_legitimate():
    entries = (
        f"{FACT},"
        '{"id":"F2","kind":"fact","label":"rev y2","value":330,'
        '"unit":"EUR_M","basis":"annual","source":"case"},'
        '{"id":"D1","kind":"derived","label":"2yr revenue","value":654,'
        '"unit":"EUR_M","basis":"cumulative_2yr","formula":"F1 + F2"}'
    )
    assert quantcheck.verify_ledger(_ledger(entries)).passed


# --- bounds (Q5) -----------------------------------------------------------------


def test_assumption_outside_its_own_band_fails():
    out = ASSUMPTION.replace('"value":0.20', '"value":0.45')
    report = quantcheck.verify_ledger(_ledger(out))
    assert any("outside its own" in d.message for d in report.defects)


def test_assumption_without_band_fails():
    unbanded = (
        '{"id":"A1","kind":"assumption","label":"x","value":0.45,'
        '"unit":"RATIO","source":"guess"}'
    )
    report = quantcheck.verify_ledger(_ledger(unbanded))
    assert any(d.check == "bounds" for d in report.defects)


# --- anchors (Q6) -----------------------------------------------------------------


def test_anchor_contradiction_caught():
    entries = (
        f"{FACT},"
        '{"id":"T1","kind":"assumption","label":"TAM","value":3000,'
        '"unit":"EUR_M","basis":"annual","source":"market research",'
        '"low":2000,"high":4000},'
        '{"id":"S1","kind":"assumption","label":"share","value":0.018,'
        '"unit":"RATIO","basis":"annual","source":"est","low":0.01,"high":0.20},'
        '{"id":"D1","kind":"derived","label":"SOM","value":54,'
        '"unit":"EUR_M","basis":"annual","formula":"T1 * S1","anchor":"F1"}'
    )
    report = quantcheck.verify_ledger(_ledger(entries))
    [defect] = [d for d in report.defects if d.check == "anchor"]
    assert "contradicts" in defect.message and "F1" in defect.ids


# --- bridges (Q7) ------------------------------------------------------------------


def test_bridge_must_be_pure_sum_of_ids():
    product = (
        f"{FACT},{ASSUMPTION},"
        '{"id":"B1","kind":"derived","label":"bridge","value":64.8,'
        '"unit":"EUR_M","basis":"annual","formula":"F1 * A1","bridge":true}'
    )
    report = quantcheck.verify_ledger(_ledger(product))
    assert any("pure sum" in d.message for d in report.defects)

    literal = (
        f"{FACT},"
        '{"id":"B1","kind":"derived","label":"bridge","value":325,'
        '"unit":"EUR_M","basis":"annual","formula":"F1 + 1","bridge":true}'
    )
    report = quantcheck.verify_ledger(_ledger(literal))
    assert any("bare literal" in d.message for d in report.defects)


# --- the EspressoLux regression (F-1..F-7) -----------------------------------------

ESPRESSOLUX_LEDGER = _ledger(
    # facts
    '{"id":"F1","kind":"fact","label":"Revenue FY26","value":324,'
    '"unit":"EUR_M","basis":"annual","source":"case: €324M"},'
    '{"id":"F2","kind":"fact","label":"TAM","value":3000,'
    '"unit":"EUR_M","basis":"annual","source":"case: €3.0B"},'
    # F-6: bean cost 45% of revenue, outside any defensible band
    '{"id":"A5","kind":"assumption","label":"Bean cost share","value":0.45,'
    '"unit":"RATIO","basis":"annual","source":"unsourced","low":0.20,"high":0.30},'
    '{"id":"A8","kind":"assumption","label":"Delivery share","value":0.20,'
    '"unit":"RATIO","basis":"annual","source":"est","low":0.10,"high":0.25},'
    '{"id":"A9","kind":"assumption","label":"Commission","value":0.30,'
    '"unit":"RATIO","basis":"annual","source":"rate card","low":0.20,"high":0.35},'
    # F-1: SOM of €54M anchored to the company's own €324M revenue
    '{"id":"S1","kind":"assumption","label":"share","value":0.018,'
    '"unit":"RATIO","basis":"annual","source":"est","low":0.01,"high":0.20},'
    '{"id":"D_SOM","kind":"derived","label":"SOM","value":54,'
    '"unit":"EUR_M","basis":"annual","formula":"F2 * S1","anchor":"F1"},'
    # F-4: the full drain (19.44) listed among "incremental" drivers
    '{"id":"D_full","kind":"derived","label":"Full delivery drain","value":19.44,'
    '"unit":"EUR_M","basis":"annual","formula":"F1 * A8 * A9"},'
    '{"id":"D_bean","kind":"derived","label":"Bean inflation","value":7.29,'
    '"unit":"EUR_M","basis":"annual","formula":"F1 * A5 * 0.05"},'
    '{"id":"W1","kind":"assumption","label":"Wage add","value":1.94,'
    '"unit":"EUR_M","basis":"annual","source":"est","low":1,"high":3},'
    '{"id":"R1","kind":"assumption","label":"Rent add","value":0.52,'
    '"unit":"EUR_M","basis":"annual","source":"est","low":0.3,"high":1},'
    # F-2 + F-4: claimed 19.47 total, but the components sum to 29.19
    '{"id":"D_drivers","kind":"derived","label":"Driver total","value":19.47,'
    '"unit":"EUR_M","basis":"annual",'
    '"formula":"D_full + D_bean + W1 + R1","bridge":true},'
    # F-5: the "unexplained OPEX" asserted with no formula
    '{"id":"D_unexplained","kind":"derived","label":"Unexplained OPEX",'
    '"value":50.19,"unit":"EUR_M","basis":"annual"},'
    # F-3/F-7: annual figure added to a cumulative one
    '{"id":"C1","kind":"fact","label":"3yr programme value","value":6.48,'
    '"unit":"EUR_M","basis":"cumulative_3yr","source":"case"},'
    '{"id":"D_mix","kind":"derived","label":"Headline value","value":25.92,'
    '"unit":"EUR_M","basis":"annual","formula":"D_full + C1"}'
)


def test_espressolux_regression_every_defect_class_fails():
    report = quantcheck.verify_ledger(ESPRESSOLUX_LEDGER)
    assert not report.passed
    messages = "\n".join(d.message for d in report.defects)
    # F-1 — SOM contradicts the revenue fact
    assert "contradicts" in messages
    # F-2/F-4 — the driver total does not tie to its own components
    assert any(d.check == "arithmetic" and "D_drivers" in d.ids for d in report.defects)
    # F-5 — narrated residual is structurally invalid
    assert "narrated number" in messages
    # F-6 — bean cost outside its plausibility band
    assert any(d.check == "bounds" and "A5" in d.ids for d in report.defects)
    # F-3/F-7 — annual + cumulative mixed in one sum
    assert any(d.check == "units" and "D_mix" in d.ids for d in report.defects)


def test_espressolux_orphan_headline_caught_by_tie_out():
    # A corrected ledger, but the report still claims the invented €21.06M.
    good = quantcheck.verify_ledger(
        _ledger(
            f"{FACT},{ASSUMPTION},"
            '{"id":"A2","kind":"assumption","label":"commission","value":0.30,'
            '"unit":"RATIO","basis":"annual","source":"rate card",'
            '"low":0.20,"high":0.35},'
            '{"id":"D1","kind":"derived","label":"drain","value":19.44,'
            '"unit":"EUR_M","basis":"annual","formula":"F1 * A1 * A2"}'
        )
    )
    assert good.passed
    case = "Revenue €324 million. EBITDA margin fell from 19% to 11%."
    report = "We unlock €21.06M in incremental EBITDA on €324M revenue."
    tie = quantcheck.tie_out(report, good.entries, case)
    assert not tie.passed
    assert "21.06" in tie.defects[0].message

    honest = "The delivery drain is €19.44M (rounded: €19.4M) on €324M revenue."
    assert quantcheck.tie_out(honest, good.entries, case).passed


def test_tie_out_scales_percent_and_billions():
    verified = quantcheck.verify_ledger(
        _ledger(
            f"{FACT},{ASSUMPTION},"
            '{"id":"T1","kind":"fact","label":"TAM","value":3000,'
            '"unit":"EUR_M","basis":"annual","source":"case"}'
        )
    )
    case = "Revenue €324 million."
    ok = "Delivery is 20% of sales in a €3.0B market; revenue €324M in FY-2029."
    assert quantcheck.tie_out(ok, verified.entries, case).passed
    bad = "Delivery is 35% of sales."
    assert not quantcheck.tie_out(bad, verified.entries, case).passed


# --- pipeline integration -----------------------------------------------------------


def _drain(coro):
    asyncio.run(coro)


def test_quant_gate_reworks_planted_error_then_passes(tmp_path, monkeypatch):
    """A broken ledger triggers a deterministic EM rework carrying the exact
    defect; the corrected ledger passes and the run completes review-ready."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "quantfix.db")
    monkeypatch.setattr(config, "MAX_REWORK", 1)
    db.reset_for_tests()

    broken = QUANT.replace('"value":8,', '"value":9,')  # 800 * 0.01 != 9
    em_calls = {"n": 0}
    rework_briefs: list[str] = []

    async def fake_call(agent, system, user, **kw):
        if agent == "engagement-manager":
            em_calls["n"] += 1
            if "QUANT GATE DEFECTS" in user:
                rework_briefs.append(user)
                return "fixed reconciliation" + QUANT
            return "reconciliation" + broken
        return fake_output(agent)

    eid = db.create_engagement("browser-x", CASE)
    _drain(run_engagement(eid, CASE, call=fake_call))

    assert em_calls["n"] == 2  # initial + one deterministic fix
    # the rework brief carries the machine-generated defect verbatim
    assert rework_briefs and "states 9" in rework_briefs[0]
    completed = next(
        e for e in db.list_events(eid) if e["type"] == "engagement_completed"
    )
    assert completed["payload"]["review_ready"] is True
    gate_events = [e for e in db.list_events(eid) if e["type"] == "quant_gate"]
    assert gate_events[-1]["payload"]["passed"] is True
    db.reset_for_tests()


def test_quant_gate_fails_closed_without_ledger(tmp_path, monkeypatch):
    """An EM that never produces a ledger exhausts the fix budget and the
    engagement completes NOT review-ready — never a confident final report."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "quantfail.db")
    monkeypatch.setattr(config, "MAX_REWORK", 1)
    db.reset_for_tests()

    async def fake_call(agent, system, user, **kw):
        if agent == "engagement-manager":
            return "reconciliation with no ledger at all"
        return fake_output(agent)

    eid = db.create_engagement("browser-x", CASE)
    _drain(run_engagement(eid, CASE, call=fake_call))

    completed = next(
        e for e in db.list_events(eid) if e["type"] == "engagement_completed"
    )
    assert completed["payload"]["review_ready"] is False
    gate_events = [e for e in db.list_events(eid) if e["type"] == "quant_gate"]
    assert gate_events[-1]["payload"]["passed"] is False
    assert "no ```quant ledger block" in gate_events[-1]["payload"]["defects"][0]
    db.reset_for_tests()


def test_tie_out_reworks_orphan_number_then_passes(tmp_path, monkeypatch):
    """A report citing a number outside the verified ledger is reworked once
    with the exact orphan list; the corrected report ships review-ready."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "tieout.db")
    db.reset_for_tests()
    report_calls = {"n": 0}

    async def fake_call(agent, system, user, **kw):
        if agent == "report-writer":
            report_calls["n"] += 1
            if "ORPHAN NUMBERS" in user:
                return "Final report: uplift €8M on $800M revenue."
            return "Final report: uplift €21.06M on $800M revenue."
        return fake_output(agent)

    eid = db.create_engagement("browser-x", CASE)
    _drain(run_engagement(eid, CASE, call=fake_call))

    assert report_calls["n"] == 2
    engagement = db.get_engagement(eid)
    assert "21.06" not in engagement["report_md"]
    completed = next(
        e for e in db.list_events(eid) if e["type"] == "engagement_completed"
    )
    assert completed["payload"]["review_ready"] is True
    db.reset_for_tests()


def test_tie_out_fails_closed_and_flags_the_report(tmp_path, monkeypatch):
    """If the orphan survives the rework, the report ships with an explicit
    not-review-ready warning naming the unverifiable figures."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "tieout_fail.db")
    db.reset_for_tests()

    async def fake_call(agent, system, user, **kw):
        if agent == "report-writer":
            return "Final report: uplift €21.06M."
        return fake_output(agent)

    eid = db.create_engagement("browser-x", CASE)
    _drain(run_engagement(eid, CASE, call=fake_call))

    engagement = db.get_engagement(eid)
    assert "QUANT GATE — NOT REVIEW-READY" in engagement["report_md"]
    assert "21.06" in engagement["report_md"]  # named, not hidden
    completed = next(
        e for e in db.list_events(eid) if e["type"] == "engagement_completed"
    )
    assert completed["payload"]["review_ready"] is False
    db.reset_for_tests()
