# StratAgent — Final Acceptance Test

**Independent Principal Engineer & Management-Consulting Partner · acceptance sign-off**
**Date:** 2026-07-11 · **Version under test:** `0.1.0-rc2` · **Method:** one complete, genuine
`/solve-case` engagement observed end-to-end, no intervention, no output improvement.

**Case (brand-new, never used):** *Fernwood Press* — a 40-year-old academic textbook publisher
($120M revenue, print −9%/yr, digital 18%, 2 of 5 divisions unprofitable, ~20-month cash runway)
asking whether it has a viable standalone future and which of three bets — (A) digital pivot,
(B) franchise concentration, (C) sale/merger — best secures value. Distinct from every pilot and
benchmark case.

**Artifacts produced:** `engagements/fernwood-digital-pivot/` — 15 markdown stages + `state.json`
+ `report.md`; telemetry trace `telemetry/eng_fernwood_press.jsonl` (15 spans).

---

## 1. Executive Summary

**Verdict: PASS.** StratAgent behaved like a real consulting platform across the entire lifecycle.
On a genuinely novel case it produced correct classification, a dependency-aware plan, an adapted
framework selection, a MECE-validated issue tree, honest analyst reasoning across five domains, a
**governance layer that materially improved the analysis**, a **passing deterministic validation
gate**, a board-quality report that preserved every assumption and incorporated every challenger
caveat, a **complete telemetry trace**, and valid state generation.

The standout was governance. The Reviewer ran genuine checks (not a rubber stamp) and the
Challenger **overturned the Reviewer's own framing** of the load-bearing assumption, surfaced an
un-valued fallback option, flagged inflated language, and caught a real execution blindspot — all
of which flowed faithfully into the final deliverable.

**Zero hallucinations were observed:** every quantitative claim was labeled `[ASSUMPTION]`/`[A:…]`
or tied to a seeded ledger assumption, and agents repeatedly stated coverage gaps rather than
inventing data. Confidence was honestly calibrated (mean 0.53; nothing above 0.8; the decision was
explicitly capped on its weakest assumptions).

One **transient infrastructure interruption** occurred (a subscription/API error on the first
knowledge-agent dispatch) — **not a StratAgent defect**; a retry succeeded and the engagement
completed. No Critical issue prevented execution.

Production posture is unchanged from the Research Evaluation: **Ready for Limited Beta under
mandatory human review** — the assumption-only evidence base and a retrieval-ranker degeneracy
(both observed here) keep it short of unsupervised production.

---

## 2. Engagement Timeline

From the telemetry trace (durations are real, observed). Active subagent time ≈ **31 minutes**; all
15 spans `finished`, none `failed`; 0 rework; 0 validation failures.

| # | Phase | Agent | Duration | Outcome |
|---|---|---|---|---|
| 1 | classify | case-classifier | 22.9 s | turnaround + M&A hybrid |
| 2 | gap_analysis | information-gap | 50.7 s | 7 gaps seeded (AL-01…07) |
| 3 | planning | planner | 43.0 s | 11-step plan, PG1 parallel |
| 4 | framing | framework-selector | 127.7 s | Playing-to-Win + CM + Exit |
| 5 | issue_tree | issue-tree-generator | 208.2 s | `validate_mece` = True, 9 leaves |
| 6 | knowledge | knowledge-agent | 130.2 s | 12 refs (retry after infra error) |
| 7–11 | analysis | financial / market / operations / risk / strategy | 672.5 s | 5 analyst blocks |
| 12 | review | reviewer | 105.1 s | **approved** |
| 13 | challenge | challenger | 176.3 s | **stands_with_caveats** |
| 14 | validation_gate | report_gate | <1 s | **passed** (exit 0) |
| 15 | reporting | report-writer | 320.6 s | report.md (137 lines) |

---

## 3. Agent-by-Agent Review

- **case-classifier** ✓ — correct turnaround(primary)+M&A(secondary) hybrid; sharp real question
  (viability + which bet before cash runs out); 5 labeled load-bearing unknowns; 20-month runway
  flagged as the hard constraint.
- **information-gap** ✓ — 7 gaps, each tagged VIABILITY vs BET-CHOICE with a seeded assumption +
  confidence + breakeven; identified overhead-coverage (AL-02) as "the master viability test" and
  flagged the two fragile foundations (AL-04 capital 0.45, AL-02 0.5); added a gap the classifier
  missed (exit-cost timing, AL-07).
- **planner** ✓ — clean dependency chain; PG1 parallel (financial/market/operations); risk
  sequential (needs pivot economics + exit cost); strategy as the integrative decision node; each
  analyst mapped to specific assumptions/breakevens.
- **framework-selector** ✓ — read the vault; selected Playing-to-Win (gated cascade) +
  Contribution-Margin + Exit Analysis, each genuinely adapted (viability screen ahead of
  where-to-play; franchise valued on *declining* volume; **exit value as the common yardstick every
  path must beat**).
- **issue-tree-generator** ✓ — ran the real `validate_mece` (valid=True, 0 violations); 9
  owned/testable leaves; explicit MECE justification (V2 asset-today vs B the-bet; A economics vs R1
  execution risk — disjoint); clean gate logic (V1+V2 fail → forces C).
- **knowledge-agent** ✓ (after retry) — retrieved genuinely relevant notes across all 5 topics;
  evidence-pinned to commit `3cb863a`; **honestly** reported coverage gaps (no turnaround/distress or
  distressed-M&A value-floor note) and a real system observation (see §8, the retrieval ranker
  returned a degenerate all-1.0 ranking, so it selected by direct inspection). No invention.
- **financial-analyst** ✓ — fully-labeled quant; beyond the seeded assumptions found the trio is
  viable-but-thin (7% EBITDA) yet **melts to −$0.6M by yr3** (breakeven CM 31%), and framed A vs C
  (C = $47–67M certain-ish floor; A ≈ $0 unfunded → ~$50–60M only if $15–25M capital secured).
- **market-analyst** ✓ — drew a distinction the assumption didn't: the 12% bar is a *growth-rate*
  test not a *dollar-offset* test (digital would need ~41% growth to offset print $-loss); OER
  zero-price anchor threatens ASPs ("watch ASP, not units").
- **operations-analyst** ✓ — genuine catch: **partial separability** — ~40% of the divisions' loss
  is sticky allocated overhead that stays, so avoidable loss is ~$2.4M/yr not $4M; divestiture sits
  *on* AL-07's danger line; net-extending only if the backlist is sold.
- **risk-analyst** ✓ — quantified L×I register; **escalated the SEVERE risk** (capital unavailable →
  A ≈ $0, score 20); named the single biggest threat — a **time-decaying value floor**; wove
  together all three upstream analysts. Honest Medium-Low confidence.
- **strategy-analyst** ✓ — decisive integration: VIABILITY possible but time-boxed (~24–30mo, not a
  going concern); C objective-preferred (AL-06 independence non-binding); recommended **C now**;
  flip-to-A only on a binding early term sheet; closing insight to test capital *in parallel*, not
  sequenced.

**Every agent stayed in role** (single responsibility, owner-exclusive writes, no cross-talk) and
preserved fact/assumption labeling. No agent invented data.

---

## 4. Governance Review

**The clearest evidence the platform is more than a one-shot answer.**

- **Reviewer (approved)** — ran all 5 checks genuinely: confirmed all 9 leaves answered, verified
  cross-analyst numbers reconcile (franchise $22.8M ⊂ trio $31.9M; breakeven CM 31% identical across
  three analysts), and produced three real, non-blocking observations — most notably distinguishing
  *inline-labeled* `[A:…]` inputs from *registered* ledger assumptions and flagging AL-04 as the
  swing before the Challenger. Separation of duties held (it authored none of the analysis).
- **Challenger (stands_with_caveats)** — genuinely adversarial and, notably, **corrected the
  Reviewer**: it argued the true load-bearing assumption is **AL-05** (a going-concern multiple on a
  self-liquidating asset, quoted as EV pre *unknown* net-debt), not AL-04; found that **Option B was
  dismissed but never valued** (the very fallback the decision could hinge on); called the *language*
  inflated ("near-certain"/"decisive" on a 0.5 stack); and caught a real execution blindspot — a
  **parallel capital-raise + sale sends contradictory signals and can depress both prices**. It did
  not manufacture objections where the recommendation survived, and correctly returned
  stands_with_caveats rather than needs_rework because the *direction* held.

Both gates ran (mandatory, per ADR-006); the challenger's precondition (reviewer approved) was met.
Governance produced material, non-obvious improvements that reached the client deliverable intact.

---

## 5. Validation Review

- **Live deterministic gate ran and PASSED** (`scripts/validate_engagement.py fernwood-digital-pivot`
  → exit 0, "render-ready and internally consistent").
- The gate constructed a valid `EngagementState` from `state.json` and enforced the RC1.2
  anti-hallucination rules: **both governance verdicts present and cleared**, every answered finding
  cites the AL-xx ledger, **all seven load-bearing assumptions carry breakevens**, and no COMPLETE
  analysis block has an unanswered finding.
- **State generation** produced a schema-valid `EngagementState` (5 analysis blocks, 7 assumptions,
  9-node issue tree, reviewer + challenge notes, recommendations). No schema errors.
- Consistency with the prior RC1.2 verification (which demonstrated the *block* path) is confirmed:
  here the *pass* path on a fresh engagement is verified. No report bypassed the gate.

---

## 6. Telemetry Review

- **Complete trace: 15 spans, zero gaps, zero `failed`.** All phases represented (classify →
  reporting) plus the validation_gate event.
- **Governance + gate outcomes captured:** `reviewer` metadata `verdict=approved`, `challenger`
  metadata `verdict=stands_with_caveats`, `report_gate` `validation_status=passed`.
- **Analytics compute correctly:** active time ~31 min; `analysis` phase 672.5 s (sum of five
  analysts); `rework_count=0`; `validation_failures=0`; `knowledge_retrieval_hits=12`;
  `frameworks_used` = the 4 selected; **confidence distribution n=5, mean 0.53, median 0.55, range
  0.45–0.60** (one value in the 0.0–0.5 bucket, four in 0.5–0.7) — matching the honest Low–Medium
  calibration the analysts reported.
- Telemetry stayed operational-only (durations/tokens/verdicts), separate from the domain log,
  correlated by `engagement_id`. Per the known design, per-agent spans were emitted by the
  orchestrator (instruction-driven) via the CLI — on this run **all 15 were captured with no
  missing spans**.

---

## 7. Final Report Review

`engagements/fernwood-digital-pivot/report.md` (137 lines) is board-quality:

- **Exec-summary discipline** — recommendation first (sell now on a hard clock; B as walk-away; A
  only on a binding term sheet), then the single biggest caveat (equity floor net of unknown debt).
- **Every `[ASSUMPTION]` label preserved**; no number upgraded to a fact.
- **All four Challenger caveats incorporated honestly:** (i) load-bearing assumption reframed to
  AL-05; (ii) value floor presented as an *equity* range with ~$34M downside and **"near-certain"
  removed**; (iii) **Option B valued**, not dismissed; (iv) the parallel-track signaling conflict +
  buyer-count/antitrust exposure addressed.
- **Honest viability verdict** (self-liquidating ~24–30mo, not a going concern) with the runway and
  time-decay kept central; full assumptions log including the Reviewer's registered-vs-inline
  distinction; explicit removal of inflated language.

Evidence traceability, assumption labeling, MECE, consistency, calibration, and report quality all
observed as **sound**.

---

## 8. Issues Found (honest capture)

No Critical issue prevented execution. Reported as observations (not recommendations):

| # | Severity | Observation |
|---|---|---|
| 1 | **Operational (transient)** | The first `knowledge-agent` dispatch failed with a subscription/API error — **an infrastructure fault, not a StratAgent defect**. A retry succeeded and the engagement completed with no data loss. |
| 2 | **Low–Medium** | **Retrieval-ranker degeneracy.** The knowledge-agent reported the retrieval adapter returned a degenerate all-1.0 ranking "dominated by KPI noise," and selected notes by direct vault inspection instead. Graceful degradation worked, but the scoring did not discriminate on this query. |
| 3 | **Low (by design)** | **Vault coverage gaps** for turnaround/distress and distressed-M&A "value floor." The agents flagged these honestly and did not invent — consistent with the empty-benchmark design. |
| 4 | **Medium (known/by-design)** | **Assumption-only evidence.** Every quantitative claim is an assumption; there are no external evidence records (the evidence-provider seam is unpopulated). Governance correctly capped confidence and the report labeled everything. |
| 5 | **Low (caught by governance)** | Several load-bearing model inputs were only *inline* `[A:…]`-labeled, not *registered* ledger assumptions. The Reviewer flagged it and the report carried it transparently — a hygiene note, not a defect. |
| — | **Informational** | The orchestration + telemetry recording + `state.json` construction were driven through the SKILL + CLIs (the live orchestrator is an LLM/markdown system, as designed); per-agent telemetry is instruction-driven, but the full trace was captured here. |

---

## 9. Pass / Fail

# ✅ PASS

StratAgent executed one complete, genuine consulting engagement on a brand-new case and behaved
like a real consulting platform at every stage: correct classification and planning, adapted
framework selection, a MECE-validated issue tree, honest multi-domain analyst reasoning, a
governance layer that measurably improved (and internally cross-checked) the analysis, a passing
deterministic validation gate, valid state generation, a complete telemetry trace, and a
board-quality report with full evidence traceability and zero observed hallucinations. The only
interruption was a transient infrastructure error external to StratAgent.

---

## 10. Production Readiness Statement

StratAgent is **Ready for Limited Beta under mandatory human review** — this acceptance run
reinforces, and does not change, the independent Research Evaluation and Release Audit.

- The **consulting engine and governance are genuinely strong** and performed at a high level here:
  the recommendation is defensible, the reasoning is traceable, the assumptions are labeled with
  breakevens, and the governance gates caught real issues (and corrected each other).
- It is **not ready for unsupervised production.** Every number is an assumption (the evidence base
  is empty by design; the provider seam is unpopulated), output is non-deterministic, and this run
  surfaced a retrieval-ranker degeneracy. A qualified human must verify every number and own the
  final recommendation before it is used — which the system's own labeling makes practical.
- Operationally the platform is sound: the live validation gate blocks un-evidenced reports, and the
  telemetry layer produced a complete, analyzable trace.

**Acceptance sign-off:** the platform passes final acceptance for its intended posture (governed,
human-reviewed decision support at Limited-Beta maturity). It is cleared to operate in that mode; it
is not cleared for production-grade, unsupervised, numeric decision-making until the evidence-base
gap is closed.

---

*Independent acceptance test — evaluation only. No source code, prompts, documentation, or
architecture were modified. The engagement's runtime artifacts (`engagements/…`, `telemetry/…`) are
git-ignored runtime output.*
