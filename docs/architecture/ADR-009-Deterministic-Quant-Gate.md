---
adr: 009
title: Deterministic Quantitative Verification (the Quant Gate)
status: Accepted (implemented 2026-07-16 — quantcheck.py + engine wiring + 25 tests)
date: 2026-07-16
deciders: [Principal Architect]
relates: [ADR-006 Governance Gates, ADR-002 §Quality Gates, dashboard pipeline engine]
supersedes: []
tags: [governance, math, verification, anti-hallucination, dashboard]
---

# ADR-009 — Deterministic Quantitative Verification (the Quant Gate)

> **Status:** Accepted & implemented (2026-07-16).
> `apps/dashboard/backend/app/pipeline/quantcheck.py` (verifier + tie-out),
> gate wiring in `engine.py`, tests in `tests/test_quantcheck.py` including
> the EspressoLux F-1..F-7 regression. Port to `packages/governance` for the
> plugin path remains a follow-up (§4-C).
> **Goal:** No number in a delivered report is ever narrated by an LLM.
> Every figure is either a client fact, a labeled assumption with declared
> bounds, or a value **recomputed deterministically by Python** from those
> inputs — and the report cannot ship if any stated number disagrees with the
> recomputation.

---

## 1. Context — the EspressoLux failure

The 2026-07-16 EspressoLux engagement (dashboard pipeline) shipped with
`reviewer=approved` while containing defects that a purely mechanical check
would have caught:

- **F-1 Self-contradictory market share.** Report claimed SOM €54M / 1.8%
  share of a €3.0B TAM while the company's own revenue (FACT A1) was €324M —
  10.8% of TAM. The answer to a client question ("are customers switching?")
  rested on the contradiction.
- **F-2 Headline number never ties.** "€21.06M incremental EBITDA" was
  decomposed three ways in the same document: 10.37+6.48+2.59 = 19.44 and
  10.37+9.00+1.94 = 21.31; neither equals 21.06.
- **F-3 Basis confusion.** The same figure was labeled "3-Yr Incremental
  EBITDA" in one table and "incremental **annual** EBITDA by Year 3" in the
  executive brief. A scenario table's "3-Yr EBITDA €35.6M" equaled the
  company's *current annual* EBITDA.
- **F-4 Double counting.** The full €19.44M delivery-commission drain was
  listed inside a set of "incremental drivers totalling €19.47M" that only
  sums with the €9.72M *incremental* figure — which itself rested on an
  unlogged assumption (delivery share doubled 10%→20%).
- **F-5 Missing variable-cost scaling.** The central finding ("€50.19M
  unexplained OPEX") ignored that ~€43.7M of the €69.66M cost growth is
  variable cost scaling with +€54M revenue at the FY-20 cost ratio. The #1
  recommended action (forensic audit) targeted a modeling artifact.
- **F-6 Implausible assumption unchecked.** "Coffee-bean cost = 45% of
  revenue" (A5) passed with no source and no plausibility band (QSR total
  COGS benchmarks ≈ 25–30%).
- **F-7 One-year inflation effects applied to a three-year window.**

All seven are deterministic-checkable. The LLM reviewer (ADR-006 gate) is the
wrong tool for arithmetic: it judges plausibly, not exactly. **Decision class:
arithmetic, unit, and consistency checking moves out of LLM judgment into
code.**

## 2. Decision

Introduce a **Quant Gate**: a deterministic verification stage between the
Engagement-Manager reconciliation and the LLM Reviewer, plus a deterministic
**report tie-out** after the report-writer. Three components:

### 2.1 The Quant Ledger — a machine-readable contract

The Engagement-Manager's canonical reconciliation MUST end with a fenced
` ```quant ` JSON block — the **Quant Ledger** — that formalizes every number
the engagement relies on. Entry schema:

```json
{
  "id": "D7",
  "kind": "fact | assumption | derived",
  "label": "Incremental delivery commission drain",
  "value": 9.72,
  "unit": "EUR_M",
  "basis": {"scope": "annual", "fy": "FY26", "real_nominal": "nominal"},
  "formula": "(A8 - A8_PRIOR) * F1 * A9",        // derived only
  "inputs": ["A8", "A8_PRIOR", "F1", "A9"],      // derived only
  "source": "client_fact | benchmark | analyst_estimate",  // fact/assumption
  "low": 0.15, "high": 0.25,                     // assumption plausibility band
  "confidence": "high | medium | low"
}
```

Rules enforced by schema, not by prose:

- **Facts** carry a quote/pointer to the case prompt (provenance).
- **Assumptions** MUST declare `source`, `low`, `high`; `value ∈ [low, high]`.
- **Derived** values MUST have a `formula` over ledger ids only — a derived
  entry with no formula is invalid. *Narrated derived numbers become
  structurally impossible.*
- One id, one value. A quantity may not be redefined.

### 2.2 `quantcheck` — the deterministic verifier

New module `apps/dashboard/backend/app/pipeline/quantcheck.py` (stdlib only,
no LLM). Parses the Quant Ledger and runs, in order:

| # | Check | Catches |
|---|-------|---------|
| Q1 | **Schema**: required fields per kind; ids unique; no literal placeholders | malformed ledger |
| Q2 | **Reference integrity**: every formula input exists; dependency graph acyclic | dangling/circular refs (also enforces the ADR-006 "no circular valuations" rule mechanically) |
| Q3 | **Arithmetic**: safe-eval each formula (AST whitelist: `+ - * / ** ()` and ledger ids) and compare to `value` with tolerance = ½ unit of the stated precision | F-2, F-4, F-5 (residuals are computed, never asserted) |
| Q4 | **Unit/basis coherence**: operands of `+`/`-` must share `unit` and `basis.scope`; a `cumulative` figure may not be cited where `annual` is declared | F-3, F-7 |
| Q5 | **Assumption bounds**: `low ≤ value ≤ high`; `source` present | F-6 |
| Q6 | **Fact consistency**: every derived value that also has an independent fact anchor (`anchor: "F1"`) must agree within tolerance | F-1 (share = revenue/TAM is *forced* to be computed from the revenue fact) |
| Q7 | **Bridge closure**: any entry flagged `bridge: true` must have inputs summing exactly to it — used for the mandatory cost/EBITDA bridge (§2.4) | F-5 |

Output: `QuantReport {passed: bool, defects: [ {check, ids, expected, stated, message} ]}` —
defect messages are exact and machine-generated ("D7 states 19.44 but formula
(A8−A8_PRIOR)·F1·A9 evaluates to 9.72").

**Gate wiring** (dashboard `engine.py`): after each `reconcile`, run
`quantcheck`. On failure, feed the defect list back into the existing
Engagement-Manager rework loop (`MAX_REWORK` bound) *before* spending an LLM
reviewer call. **Fails closed**: if the ledger still fails after rework,
`review_ready = False` and the existing honest-interim-report path fires. A
missing/unparseable ` ```quant ` block is itself a failure — the gate cannot
be skipped by omission.

### 2.3 Report tie-out — no orphan numbers

After the `reporting` phase, a deterministic scanner extracts every numeric
claim from the report markdown (`€xM`, `x%`, `x.x pp`, plain magnitudes) and
requires each to match, within rounding, either (a) a Quant Ledger value, or
(b) a number literally present in the case prompt. Orphans → one bounded
report-writer rework pass with the exact orphan list ("€21.06M appears in
§Exec Brief; nearest ledger value is D12=€19.44M"). Still failing →
`review_ready = False`.

The report-writer prompt gains one rule: *every figure you write must be a
ledger value cited by id; you may round for prose but never re-derive.*

### 2.4 The mandatory bridge (kills F-5 class errors)

For any profitability/cost case, the financial-analyst and Engagement-Manager
contracts require a **bridge entry set** in the ledger: period-over-period
EBITDA (or cost) change decomposed as
`volume/revenue-scaling + price/inflation + mix + one-off + residual`,
with `bridge: true` so Q7 forces exact closure. The *residual* is a derived
row — computed, never narrated — so "€50M unexplained" can only appear if the
arithmetic actually leaves €50M unexplained after variable-cost scaling.

### 2.5 Prompt-side changes (supporting, not load-bearing)

- **information-gap**: every assumption seeded with `source`, `low`, `high`,
  and provenance question ("where would this number come from: POS, CRM,
  financials, benchmark?"). Unsourced load-bearing assumptions are marked
  `OPEN` rather than silently adopted.
- **challenger**: add a model-attack checklist (run-rate vs cumulative? what
  single input flips the verdict? does the bridge close?) — the killer-question
  layer. The challenger *reads* the QuantReport, so its attack starts from
  verified numbers.
- **reviewer**: relieved of arithmetic (it demonstrably cannot do it);
  re-scoped to judgment: MECE, causality, evidence quality, calibration.

## 3. Correctness guarantee — scope and honesty

The gate makes four properties **provable**: (1) every derived figure equals
its formula's value; (2) every bridge closes exactly; (3) no report number
exists outside the ledger; (4) no quantity has two values. It does **not**
prove assumptions are *true* — an assumption inside its declared band can
still be wrong about the world. That residual risk is exactly what the
assumption ledger, breakeven columns, and challenger exist for, and it is now
the *only* residual risk, cleanly separated from arithmetic risk (which goes
to zero).

Floating-point: comparisons use `decimal.Decimal` with tolerance ½ ULP of
stated precision (a value shown as €9.72M tolerates ±€0.005M). Exact-closure
checks (Q7) use exact decimal sums.

## 4. Alternatives considered

- **A. Give analysts a calculator tool (tool-use).** Rejected as primary:
  the dashboard is multi-provider (free tiers, BYOK) with uneven tool-use
  support, and tool-use guarantees the *calculation* is right, not that the
  *report* cites it. Post-hoc verification is provider-agnostic and gates the
  actual deliverable. (Tool-use can be added later as an accelerant; the gate
  stays.)
- **B. Harder LLM reviewer prompt ("check the math carefully").** Rejected:
  the EspressoLux reviewer already had instructions to check consistency and
  approved F-1..F-7. LLM arithmetic is not a guarantee at any prompt strength.
- **C. Full `EngagementState`/`packages` integration first.** Deferred: the
  core `packages/reporting/validation.py` layer is the right long-term home,
  but the dashboard (where engagements actually run today) passes markdown,
  not `EngagementState`. Ship the gate on the live path first; port the same
  `quantcheck` contract into `packages/governance` for the plugin/skill path
  as a follow-up (the ledger format is shared by design).

## 5. Consequences

- **+** Arithmetic/unit/consistency error rate in delivered reports: zero by
  construction; failures degrade to an honest interim report, never a wrong
  confident one.
- **+** Deterministic defect messages make EM rework converge fast (the fix
  is named exactly), and cost nothing (no LLM call to detect).
- **+** Reviewer LLM budget refocuses on judgment, where it adds value.
- **−** One more contract for the EM to satisfy; expect +1 rework cycle on
  early runs until the prompt settles. Mitigation: ledger examples in the EM
  system prompt; lessons loop already captures recurring misses.
- **−** Free-form "color" numbers in prose (e.g. "~1,200 competitors") must
  enter the ledger as assumptions or be dropped — intentional.

## 6. Test plan

- Unit: golden ledgers for each check Q1–Q7 (pass + fail cases), including a
  **regression ledger encoding EspressoLux F-1..F-7** — all seven must fail.
- Property: random DAG ledgers — verifier accepts iff recomputation matches.
- Integration: pipeline test with a stubbed `call` returning a ledger with a
  planted arithmetic error → assert rework triggered with the exact defect,
  then passes on corrected ledger; orphan-number report → tie-out rework.
- E2E: rerun the EspressoLux case prompt; assert the delivered report's
  numbers all tie (script recomputes from the shipped ledger).
