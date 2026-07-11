# StratAgent Limited Beta — Program Guide

**Owner:** Product Evaluation Lead · **Status:** Design (not yet launched)
**System under test:** StratAgent `0.1.0-rc2` (RC1.2) · **Preceding evidence:**
[v1.0 Research Evaluation](../reviews/v1.0-Research-Evaluation.md) — verdict
*Ready for Limited Beta*.

This guide is the umbrella. Operational artifacts:
[Participant Instructions](Participant-Instructions.md) ·
[Evaluation Forms](Evaluation-Forms.md) ·
[Scoring Rubric](Scoring-Rubric.md) ·
[Success Metrics](Success-Metrics.md) ·
[Release Checklist](Release-Checklist.md) ·
[Go/No-Go Framework](Go-No-Go-Framework.md).

---

## 0. Why a Limited Beta, and what it must prove

The internal evaluation reached three conclusions that shape this program:

1. **Quality is real but unproven at scale** (mean 7.6/10, n=3). Beta must
   generate a genuine sample (target ≥100 engagements) so quality can be measured
   with real distributions, per-archetype and per-segment.
2. **Every quantitative claim is a labeled assumption, not sourced evidence** (the
   knowledge vault ships no benchmarks). Beta must run with **human review of all
   numbers** and measure how much users trust/edit them.
3. **The differentiator is governance, not the one-liner** (Reviewer + Challenger
   caught overconfidence and blindspots a single-pass model shipped). Beta must
   test whether *real users* perceive and value that.

**The three questions beta must answer for GA:**
- Do real users find the recommendations **useful and trustworthy** enough to act
  on (after review)?
- Is the **assumption-heavy** output acceptable, or is a populated Evidence
  Provider a hard prerequisite for GA?
- Where does the workflow **break down** for non-expert users?

---

## 1. Program at a glance

| Parameter | Value |
|---|---|
| Duration | 6 weeks (1 onboarding, 4 active, 1 debrief) |
| Cohort size | 20–30 participants across 5 segments |
| Engagements/participant | 3–5 (≥1 guided benchmark + ≥2 bring-your-own) |
| Target total engagements | ~100 (enough for per-archetype signal; fixes the eval's n=3 gap) |
| Access | Supervised — every final report requires human review before use |
| Cost/latency note | Each engagement is ~11–13 model dispatches, minutes to tens of minutes |

---

## 2. Phase 1 — Beta cohort

Selection principle: prioritize users who can **supply their own data** (to
compensate for the empty evidence base) and who can **judge output quality**.

| Segment | Why they fit | Experience | Expected usage | Recommended complexity |
|---|---|---|---|---|
| **Junior/mid consultants** (primary) | Judge consulting quality; value structure + auditability | 1–5 yrs strategy/ops | 4–5 engagements | A2–A3 (moderate → open) |
| **Corporate strategy teams** (primary) | Bring real data + real decisions; assess usefulness | Mixed, 3–15 yrs | 3–4 engagements, real problems | A1–A2 (data-backed) |
| **MBA students** (secondary) | High volume, case-fluent, calibratable | Pre-experience → 5 yrs | 5 engagements, benchmark-heavy | A1–A2 |
| **Startup founders** (secondary) | Real high-stakes decisions; test "act on it" willingness | Varies | 2–3 real engagements | A2 |
| **Business analysts / PMs** (tertiary) | Data-literate; test non-expert usability | 1–8 yrs | 3 engagements | A1–A2 |

**Deliberately under-weighted for Limited Beta:** users who cannot supply data
*and* cannot judge quality (the empty evidence base makes them a poor signal and a
higher risk of over-trusting assumptions). Revisit at GA once an Evidence
Provider is populated.

**Complexity tiers** (from the research benchmark): **A1** bounded (clear
decision + numbers), **A2** moderate (facts missing → assumptions), **A3** open
(no numbers / soft / political).

---

## 3. Phase 2 — Tasks (representative engagements)

Each participant completes a **mix**: one *guided* benchmark case (for
cross-participant calibration) plus two-plus *bring-your-own (BYO)* real problems.
Benchmark cases are drawn from [the 30-case benchmark](../reviews/v1.0-Validation-Benchmark.md).

| Archetype | Guided benchmark case | BYO prompt to participants |
|---|---|---|
| Profitability | C01 Meridian Fasteners | "A unit whose margin fell — why, and what to fix first?" |
| Market entry | C04 Northwind Cloud | "A market/geography you're considering entering." |
| Pricing | C07 Palisade / C08 TorqueLine | "A pricing model or discount problem you face." |
| Operations / supply chain | C21 Ironwood / C22 Petal & Stem | "A cost/service/throughput problem in your operation." |
| Digital transformation | C17 Frontenac / C29 Cardinal | "A modernization decision you're weighing." |
| Organizational design | C19 Aperture / C20 Harbor & Vine | "A structure/incentive/ownership problem." |
| M&A | C13 Summit / C14 Vector | "An acquisition/merger you're evaluating." |
| Growth | C11 Loopwork / C12 Cordillera | "A stalled-growth decision." |

Rules given to participants: **do not hand-improve the output**; run the real
`/solve-case` flow; supply your own facts/data where you have them; record what
you did in the [post-engagement form](Evaluation-Forms.md).

Assignment: each participant gets **2 guided cases spanning ambiguity tiers**
(one A1, one A3) + their BYO cases, so we observe the system on both bounded and
open problems per person.

---

## 4. Phase 6 — Ethics (summary; full policy below)

Non-negotiable framing communicated to every participant:

- **StratAgent is decision *support*, not a decision-maker.** A qualified human
  reviews every recommendation before it is used.
- **Numbers are assumptions, not facts.** Unless the participant supplied the
  data, treat every figure as `[ASSUMPTION]` — the report labels them; reviewers
  must check each one.
- **Unsupported uses** (regulated financial/legal/medical advice, live trading,
  irreversible high-stakes decisions without expert review) are prohibited during
  beta.

Full policy, known risks, and required-review rules: **[Ethics & Appropriate
Use](#5-ethics--appropriate-use-full)** below.

---

## 5. Ethics & Appropriate Use (full)

### 5.1 Appropriate use
- Structuring a problem; generating a first-draft issue tree, analysis, and a
  challenged recommendation to react to and refine.
- Stress-testing your own thinking (the Challenger is the highest-value part).
- Learning consulting structure (MBA/analyst upskilling).

### 5.2 Limitations (state to every user)
- **No sourced data.** The vault holds frameworks, not benchmarks; every number
  is a labeled assumption unless you supplied it.
- **Non-deterministic.** The same prompt can yield different recommendations on
  re-run; treat output as one reasoned draft, not "the answer."
- **No real-time information.** No live market, financial, or news data.
- **Model-family blind spots.** The Challenger mitigates but does not eliminate
  overconfidence and blindspots.

### 5.3 Required human review (hard rule)
Before any StratAgent output is used or shared: a qualified human must (a) verify
**every** quantitative claim against real data, (b) confirm the load-bearing
assumptions and their breakevens are acceptable, and (c) own the final
recommendation. The report's **Assumptions Ledger** and **Challenger verdict**
are the audit surface for this review.

### 5.4 Known risks
Overconfidence on assumption-backed numbers; missing evidence presented
confidently; blindspots outside the issue tree; possibility of hallucination
(none observed in evaluation, but not guaranteed); over-trust by non-expert users.

### 5.5 Unsupported use cases (prohibited in beta)
Regulated financial advice, legal advice, medical/clinical decisions, live
trading or capital allocation executed without human sign-off, safety-critical or
irreversible decisions, any use where an unverified number could cause material
harm, and any decision presented to a third party as validated fact.

---

## 6. Timeline

| Week | Activity |
|---|---|
| 0 | Recruit + screen cohort; consent + ethics acknowledgment; onboarding session |
| 1 | Guided benchmark case each (calibration); collect first forms |
| 2–4 | BYO engagements; weekly pulse survey; 8–10 mid-program interviews |
| 5 | End-of-program survey; segment/usage analysis; remaining interviews |
| 6 | Synthesis → Go/No-Go review against the [framework](Go-No-Go-Framework.md) |

Success is judged against [Success Metrics](Success-Metrics.md) and the
[Go/No-Go Framework](Go-No-Go-Framework.md).
