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

import pytest

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


def test_oversized_exponent_rejected():
    """A huge integer exponent is refused (bounded work; no real formula needs
    a power > 100) — defense against a pathological ledger."""
    huge = (
        f"{FACT},"
        '{"id":"D1","kind":"derived","label":"x","value":1,'
        '"unit":"EUR_M","formula":"F1 ** 1000000"}'
    )
    report = quantcheck.verify_ledger(_ledger(huge))
    assert any("out of range" in d.message for d in report.defects)


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


def test_tie_out_matches_a_negative_ledger_value():
    """2026-07-21 real-engagement finding: a correctly-cited negative ledger
    value (ROIC = -4%) was flagged as an "orphan number". Root cause: the
    number-matching regex had no sign group at all, so "-4%" and "4%" parsed
    to the identical positive Decimal — a negative ledger entry could never
    tie out against its own correct citation, regardless of unit/scale. Fixed
    by capturing a leading -/−/– as a sign, but only when it is not itself
    preceded by a digit (so a range like "62-75%" still tokenizes as two
    positive numbers, not a false negative)."""
    verified = quantcheck.verify_ledger(
        _ledger(
            '{"id":"R1","kind":"assumption","label":"Aggregate ROIC for new '
            'initiatives","value":-0.04,"unit":"RATIO","basis":"annual",'
            '"source":"analyst_estimate","low":-0.10,"high":0.0}'
        )
    )
    assert verified.passed

    correctly_cited = "New initiatives deliver -4% ROIC against WACC. [R1]"
    assert quantcheck.tie_out(correctly_cited, verified.entries, "").passed

    # The en-dash variant an LLM commonly emits for a negative figure.
    en_dash_cited = "New initiatives now deliver ROIC of –4%. [R1]"
    assert quantcheck.tie_out(en_dash_cited, verified.entries, "").passed

    # A genuinely wrong sign must still fail — this is not a blanket pass.
    wrong_sign = "New initiatives deliver +4% ROIC against WACC. [R1]"
    assert not quantcheck.tie_out(wrong_sign, verified.entries, "").passed

    # Range separator: the hyphen is digit-adjacent, never a sign — "75%" (the
    # only half of the range with a material suffix) must be flagged as a
    # plain positive orphan, not skipped or mistaken for "-75%".
    unrelated_range = "Utilization sits at 62-75% across the network."
    range_report = quantcheck.tie_out(unrelated_range, verified.entries, "")
    assert not range_report.passed
    assert "orphan number 75 %" in range_report.defects[0].message


@pytest.mark.parametrize(
    ("report_figure", "ledger_value", "ledger_unit", "low", "high"),
    [
        ("-4%", "-0.04", "RATIO", "-1", "1"),  # negative ROIC
        ("-12.5%", "-0.125", "RATIO", "-1", "1"),  # negative margin, decimals
        ("€-35M", "-35", "EUR_M", "-100", "0"),  # currency, sign after symbol
        ("–4%", "-0.04", "RATIO", "-1", "1"),  # en-dash (common LLM output)
        ("-€120M", "-120", "EUR_M", "-200", "0"),  # sign before symbol
        ("-8.75%", "-0.0875", "RATIO", "-1", "1"),  # negative growth rate
    ],
)
def test_signed_numbers_reconcile_across_currency_ratio_and_decimal_forms(
    report_figure, ledger_value, ledger_unit, low, high
):
    """Phase 1 regression matrix (2026-07-21 remediation): every signed form
    a report might state — plain percent, decimal-precision percent, currency
    before/after the sign, and the en-dash an LLM commonly substitutes for a
    hyphen — must reconcile against its ledger value. Positive values and
    ratios/decimals are covered by the existing suite; this pins the negative
    forms specifically, since the sign-drop bug affected negatives only."""
    verified = quantcheck.verify_ledger(
        _ledger(
            f'{{"id":"N1","kind":"assumption","label":"Signed test value",'
            f'"value":{ledger_value},"unit":"{ledger_unit}","basis":"annual",'
            f'"source":"analyst_estimate","low":{low},"high":{high}}}'
        )
    )
    assert verified.passed
    report = f"The figure is {report_figure}. [N1]"
    result = quantcheck.tie_out(report, verified.entries, "")
    assert result.passed, [d.message for d in result.defects]


def test_bare_negative_decimal_with_no_currency_or_suffix_is_not_material():
    """A bare "-0.04" with no %, currency, or comma is prose structure by the
    SAME pre-existing rule that already exempts a bare positive number (e.g.
    "3 options") — unrelated to the sign fix, confirmed here so it is not
    mistaken for a regression: it is unchanged, intentional behavior. Stated
    as -4% (the form the ledger's RATIO unit would actually appear in prose),
    it reconciles correctly, per the parametrized test above."""
    assert quantcheck._report_numbers("The internal figure was -0.04.") == []


def test_unresolved_unknowns_ignores_a_label_never_discussed():
    report = "This report is entirely about pricing strategy."
    result = quantcheck.unresolved_unknowns(report, ("Factory utilization",))
    assert result.passed


def test_unresolved_unknowns_flags_a_discussed_unknown_without_framing():
    report = "We recommend consolidation because factory utilization is low."
    result = quantcheck.unresolved_unknowns(report, ("factory utilization",))
    assert not result.passed
    assert result.defects[0].check == "unknown_evidence"
    assert "factory utilization" in result.defects[0].message


def test_unresolved_unknowns_passes_when_framed_as_evidence_insufficient():
    report = (
        "Factory utilization: Evidence Insufficient — recommend a "
        "plant-level utilization study before acting."
    )
    result = quantcheck.unresolved_unknowns(report, ("factory utilization",))
    assert result.passed


def test_unresolved_unknowns_is_a_noop_with_no_unknowns():
    result = quantcheck.unresolved_unknowns("Anything at all.", ())
    assert result.passed
    assert result.defects == ()


# --- decision policy gate (Issue 3, 2026-07-21) ------------------------------

_RECOMMENDATION_UNCONDITIONAL = (
    "## Recommendation\n"
    "Immediately halt capacity expansion based on utilization [A2].\n\n"
    "## Risks\nSome risk text.\n"
)
_RECOMMENDATION_CONDITIONAL = (
    "## Recommendation\n"
    "This recommendation is contingent upon validation of Assumption A2.\n\n"
    "## Risks\nSome risk text.\n"
)


def test_policy_gate_blocks_an_unconditional_load_bearing_recommendation():
    result = quantcheck.load_bearing_recommendation_gate(
        _RECOMMENDATION_UNCONDITIONAL, ("A2",)
    )
    assert not result.passed
    assert result.defects[0].check == "load_bearing_recommendation"
    assert result.defects[0].ids == ("A2",)


def test_policy_gate_passes_a_conditioned_load_bearing_recommendation():
    result = quantcheck.load_bearing_recommendation_gate(
        _RECOMMENDATION_CONDITIONAL, ("A2",)
    )
    assert result.passed


@pytest.mark.parametrize(
    "qualifier",
    [
        "This recommendation is contingent upon validation of Assumption A2.",
        "Evidence Insufficient to finalize this recommendation [A2].",
        "Recommended, subject to validation of [A2].",
        "This is a provisional recommendation pending [A2].",
        "Conditional upon [A2] being confirmed, we recommend X.",
    ],
)
def test_policy_gate_accepts_every_documented_qualifying_phrase(qualifier):
    report = f"## Recommendation\n{qualifier}\n\n## Risks\ntext\n"
    result = quantcheck.load_bearing_recommendation_gate(report, ("A2",))
    assert result.passed, [d.message for d in result.defects]


def test_policy_gate_ignores_a_load_bearing_id_never_cited_in_recommendation():
    """The same load-bearing assumption may be freely discussed in Analysis —
    the policy binds the board-facing Recommendation section specifically."""
    report = (
        "## Analysis\nUtilization [A2] is a key concern.\n\n"
        "## Recommendation\nDo X based on facts [A1].\n"
    )
    result = quantcheck.load_bearing_recommendation_gate(report, ("A2",))
    assert result.passed


def test_policy_gate_is_a_noop_without_a_recommendation_heading():
    result = quantcheck.load_bearing_recommendation_gate(
        "No headings at all, just prose citing [A2].", ("A2",)
    )
    assert result.passed


def test_policy_gate_is_a_noop_with_no_load_bearing_ids():
    """Facts, derived values, and supporting/material assumptions all permit
    an unconditional recommendation -- only load_bearing IDs are checked."""
    result = quantcheck.load_bearing_recommendation_gate(
        _RECOMMENDATION_UNCONDITIONAL, ()
    )
    assert result.passed


# --- pipeline integration: decision policy gate + retry-before-termination --

_QUANT_LOAD_BEARING = QUANT.replace(
    '"low":0.005,"high":0.02}', '"low":0.005,"high":0.02,"criticality":"load_bearing"}'
)


def test_engine_blocks_an_unconditional_recommendation_on_a_load_bearing_assumption(
    tmp_path, monkeypatch
):
    """End-to-end proof the decision policy gate (Issue 3) is actually wired
    into run_engagement, not just unit-tested in isolation: A1 is
    load_bearing in the ledger, the report-writer states it unconditionally,
    and the engagement must complete NOT review-ready."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "policy_block.db")
    db.reset_for_tests()

    async def fake_call(agent, system, user, **kw):
        if agent == "engagement-manager":
            return "reconciliation" + _QUANT_LOAD_BEARING
        if agent == "report-writer":
            return (
                "## Recommendation\nImmediately act on margin uplift [A1].\n\n"
                "## Risks\ntext\n"
            )
        return fake_output(agent)

    eid = db.create_engagement("browser-x", CASE)
    _drain(run_engagement(eid, CASE, call=fake_call))

    engagement = db.get_engagement(eid)
    assert engagement["status"] == "completed"
    completed = next(
        e for e in db.list_events(eid) if e["type"] == "engagement_completed"
    )
    assert completed["payload"]["review_ready"] is False
    db.reset_for_tests()


def test_engine_permits_a_conditioned_recommendation_on_a_load_bearing_assumption(
    tmp_path, monkeypatch
):
    """The other half of the proof above: the SAME load-bearing ledger, but a
    report-writer that correctly conditions the recommendation, must not be
    blocked by the decision policy gate (though it may still be blocked by
    other, unrelated gates — this fixture's ledger and report are otherwise
    clean, so review_ready should be True)."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "policy_pass.db")
    db.reset_for_tests()

    async def fake_call(agent, system, user, **kw):
        if agent == "engagement-manager":
            return "reconciliation" + _QUANT_LOAD_BEARING
        if agent == "report-writer":
            return (
                "## Recommendation\nThis recommendation is contingent upon "
                "validation of Assumption A1.\n\n## Risks\ntext\n"
            )
        return fake_output(agent)

    eid = db.create_engagement("browser-x", CASE)
    _drain(run_engagement(eid, CASE, call=fake_call))

    completed = next(
        e for e in db.list_events(eid) if e["type"] == "engagement_completed"
    )
    assert completed["payload"]["review_ready"] is True
    db.reset_for_tests()


def test_engine_manager_retries_before_terminating_on_a_missing_ledger(
    tmp_path, monkeypatch
):
    """Issue 2 resilience requirement: retry within configured limits BEFORE
    terminating. quant_verified's own budget is (MAX_REWORK + 1) reconcile
    reworks on top of the one initial reconcile call, so raising MAX_REWORK
    to 2 must grant 4 total engagement-manager calls before
    EngagementManagerValidationError fires — proving the early-termination
    hardening does not skip the existing retry/failover budget, it only acts
    once that budget is spent."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "retry_before_fail.db")
    monkeypatch.setattr(config, "MAX_REWORK", 2)
    db.reset_for_tests()
    em_calls = {"n": 0}

    async def fake_call(agent, system, user, **kw):
        if agent == "engagement-manager":
            em_calls["n"] += 1
            return "reconciliation with no ledger at all"
        return fake_output(agent)

    eid = db.create_engagement("browser-x", CASE)
    _drain(run_engagement(eid, CASE, call=fake_call))

    assert em_calls["n"] == config.MAX_REWORK + 2  # 1 initial + (MAX_REWORK+1) reworks
    engagement = db.get_engagement(eid)
    assert engagement["status"] == "failed"
    db.reset_for_tests()


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
    engagement fails closed — terminated explicitly (2026-07-21 hardening),
    never a confident final report and never a wasted review/challenge/
    report-writer pass over nothing. See
    test_missing_ledger_terminates_the_engagement_instead_of_shipping_a_report
    for the full scenario this pins the short version of."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "quantfail.db")
    monkeypatch.setattr(config, "MAX_REWORK", 1)
    db.reset_for_tests()

    async def fake_call(agent, system, user, **kw):
        if agent == "engagement-manager":
            return "reconciliation with no ledger at all"
        return fake_output(agent)

    eid = db.create_engagement("browser-x", CASE)
    _drain(run_engagement(eid, CASE, call=fake_call))

    engagement = db.get_engagement(eid)
    assert engagement["status"] == "failed"
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


def test_tie_out_rework_loop_honours_a_raised_max_rework(tmp_path, monkeypatch):
    """2026-07-21 finding: the tie-out rework was exactly one hardcoded retry,
    regardless of config.MAX_REWORK — a live engagement where the first retry
    only partially fixed the orphan list shipped as failed with no further
    chance to converge. Now bounded by MAX_REWORK like the ledger-fix loop:
    raising it to 2 must grant a second retry (3 total report-writer calls),
    and the engagement converges on the attempt the ledger-fix budget alone
    would not have reached."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "tieout_maxrework.db")
    monkeypatch.setattr(config, "MAX_REWORK", 2)
    db.reset_for_tests()
    report_calls = {"n": 0}

    async def fake_call(agent, system, user, **kw):
        if agent == "report-writer":
            report_calls["n"] += 1
            if report_calls["n"] <= 2:
                return "Final report: uplift €21.06M on $800M revenue."
            return "Final report: uplift €8M on $800M revenue."
        return fake_output(agent)

    eid = db.create_engagement("browser-x", CASE)
    _drain(run_engagement(eid, CASE, call=fake_call))

    assert report_calls["n"] == 3  # initial + 2 reworks, not capped at 1
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
    md = engagement["report_md"]
    assert "NOT BOARD-READY — INTERIM STATUS ONLY" in md
    assert "quant-gate=FAILED" in md  # governance line can't read all-clear
    assert "PROVISIONAL" in md  # recommendations demoted, not final
    assert "21.06" in md  # the orphan is named, not hidden
    completed = next(
        e for e in db.list_events(eid) if e["type"] == "engagement_completed"
    )
    assert completed["payload"]["review_ready"] is False
    db.reset_for_tests()


def test_missing_ledger_terminates_the_engagement_instead_of_shipping_a_report(
    tmp_path, monkeypatch
):
    """2026-07-21 orchestration hardening, superseding the OLD behavior this
    test used to pin (an interim report with a "no ledger found" banner):
    a live Project Atlas engagement hit a severe Gemini free-tier outage
    (confirmed via Railway logs — 10+ consecutive 503/timeout/rate-limit
    failures across the whole pooled chain, twice, for the
    engagement-manager phase specifically) that left the EM's reconciliation
    with NO atoms/quant block at all, even after its full rework budget.

    The OLD design let this proceed through reviewer, challenger, and
    report-writer anyway ("still review the substance so the rework is
    complete") — spending three more provider calls on a reconciliation
    known to be structurally unusable, and producing a confusing interim
    report instead of a clear, fast, honest failure. The Quant Gate itself
    was never the bug (it correctly detected the missing ledger both times);
    the fix is architectural: when quant.entries is None (nothing at all to
    review, as opposed to a ledger that exists but has some other verified
    defect — see test_ledger_with_a_recoverable_defect_still_reaches_report
    below for that unchanged path), stop immediately rather than continue."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "missing_ledger_stops.db")
    monkeypatch.setattr(config, "MAX_REWORK", 1)
    db.reset_for_tests()

    reviewer_called = {"n": False}

    async def fake_call(agent, system, user, **kw):
        if agent == "engagement-manager":
            return "reconciliation with no ledger at all"  # never emits one
        if agent == "reviewer":
            reviewer_called["n"] = True
        return fake_output(agent)

    eid = db.create_engagement("browser-x", CASE)
    _drain(run_engagement(eid, CASE, call=fake_call))

    engagement = db.get_engagement(eid)
    assert engagement["status"] == "failed"
    assert engagement["report_md"] is None
    assert "provider outage" in engagement["error"] or "Please try running" in (
        engagement["error"] or ""
    )
    # The whole point: three more provider calls (reviewer, challenger,
    # report-writer) never happen on a reconciliation known to be unusable.
    assert reviewer_called["n"] is False
    failed_event = next(
        e for e in db.list_events(eid) if e["type"] == "engagement_failed"
    )
    assert "Please try running the engagement again" in failed_event["payload"]["error"]
    db.reset_for_tests()


def test_ledger_with_a_recoverable_defect_still_reaches_report(tmp_path, monkeypatch):
    """Regression guard for the hardening above: a ledger that EXISTS but has
    some other verified defect (wrong arithmetic, in this case) is NOT the
    "nothing to review" case — quant.entries is a real dict here, just with
    a Q3 arithmetic defect — so the existing "review the substance so the
    rework is complete" path must still run unchanged, ending in the
    existing interim-report banner, not the new early-termination error."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "recoverable_defect.db")
    monkeypatch.setattr(config, "MAX_REWORK", 1)
    db.reset_for_tests()

    broken = QUANT.replace('"value":8,', '"value":9,')  # 800 * 0.01 != 9

    async def fake_call(agent, system, user, **kw):
        if agent == "engagement-manager":
            return "reconciliation" + broken  # a real, present, but wrong ledger
        return fake_output(agent)

    eid = db.create_engagement("browser-x", CASE)
    _drain(run_engagement(eid, CASE, call=fake_call))

    engagement = db.get_engagement(eid)
    assert engagement["status"] == "completed"  # not "failed" — reached the end
    md = engagement["report_md"]
    assert "NOT BOARD-READY — INTERIM STATUS ONLY" in md
    assert "quant-gate=FAILED" in md
    db.reset_for_tests()
    completed = next(
        e for e in db.list_events(eid) if e["type"] == "engagement_completed"
    )
    assert completed["payload"]["review_ready"] is False
    tie_events = [e for e in db.list_events(eid) if e["type"] == "quant_tie_out"]
    assert tie_events[-1]["payload"]["passed"] is False
    db.reset_for_tests()


def test_interim_banner_caps_a_long_defect_list(tmp_path, monkeypatch):
    """A ledger that fails on many rows must not bury the report under a wall of
    near-identical lines — the banner caps the list and summarizes the rest."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "cap_defects.db")
    monkeypatch.setattr(config, "MAX_REWORK", 0)
    db.reset_for_tests()

    # A ledger with 15 unsourced assumptions → 15 schema defects, all similar.
    entries = ",".join(
        f'{{"id":"A{i}","kind":"assumption","label":"x{i}","value":1,"unit":"RATIO"}}'
        for i in range(15)
    )
    bad_ledger = "reconciliation\n\n```quant\n[" + entries + "]\n```\n"

    async def fake_call(agent, system, user, **kw):
        if agent == "engagement-manager":
            return bad_ledger
        if agent == "report-writer":
            return "## Executive summary\n\nDo the thing."
        return fake_output(agent)

    eid = db.create_engagement("browser-x", CASE)
    _drain(run_engagement(eid, CASE, call=fake_call))

    md = db.get_engagement(eid)["report_md"]
    assert "NOT BOARD-READY" in md
    assert "and " in md and "more deterministic defect" in md  # cap summary line
    # only the first 8 defect bullets are shown, not all 15
    assert md.count("> - ") <= 9  # 8 defects + possibly the summary bullet
    db.reset_for_tests()


def test_reflector_sees_quant_gate_defects_not_just_reviewer_notes(
    tmp_path, monkeypatch
):
    """User-flagged gap (2026-07-17): two live interim reports (EspressoLux,
    NordWear) both failed via the quant gate, but the reflector's only
    learned lessons were generic ("test breakeven thresholds") because the
    reviewer is explicitly told arithmetic is pre-verified and never mentions
    ledger defects — so the reflector never saw the actual, specific,
    mechanical failure pattern. Assert the reflector's prompt now carries the
    quant-gate defects verbatim whenever the ledger failed, and is told to
    prioritize ledger-discipline lessons over generic advice.

    Uses a ledger that EXISTS but has a wrong-arithmetic defect, not a
    totally-missing one — 2026-07-21 hardening now terminates the engagement
    before the reflector ever runs when there is nothing at all to review
    (see test_missing_ledger_terminates_the_engagement_instead_of_shipping_a_report);
    this test's own subject (the reflector learning from a REAL, present,
    but wrong ledger) is unaffected by that change and still applies."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "reflect_quant.db")
    monkeypatch.setattr(config, "MAX_REWORK", 1)
    db.reset_for_tests()
    reflector_prompts: list[str] = []
    broken = QUANT.replace('"value":8,', '"value":9,')  # 800 * 0.01 != 9

    async def fake_call(agent, system, user, **kw):
        if agent == "engagement-manager":
            return "reconciliation" + broken
        if agent == "reflector":
            reflector_prompts.append(user)
            return "LESSON: Always give every assumption a source and a band."
        return fake_output(agent)

    eid = db.create_engagement("browser-x", CASE)
    _drain(run_engagement(eid, CASE, call=fake_call))

    assert len(reflector_prompts) == 1
    prompt = reflector_prompts[0]
    assert "Quant-gate defects" in prompt
    assert "NOT judgment calls" in prompt
    assert "highest-leverage" in prompt
    lessons = db.list_lessons()
    assert any("source" in row["text"] for row in lessons)
    db.reset_for_tests()


def test_reflector_gets_no_quant_section_when_ledger_is_clean(tmp_path, monkeypatch):
    """When the gate passes, the reflector prompt stays as before — no empty
    or misleading quant section clutters a genuinely clean run."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "reflect_clean.db")
    db.reset_for_tests()
    reflector_prompts: list[str] = []

    async def fake_call(agent, system, user, **kw):
        if agent == "reflector":
            reflector_prompts.append(user)
            return "NONE"
        return fake_output(agent)

    eid = db.create_engagement("browser-x", CASE)
    _drain(run_engagement(eid, CASE, call=fake_call))

    assert len(reflector_prompts) == 1
    assert "Quant-gate defects" not in reflector_prompts[0]
    db.reset_for_tests()
