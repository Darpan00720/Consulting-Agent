# StratAgent Beta — Success Metrics & Quantitative Analysis

Defines the metrics (Phase 3), acceptance/failure thresholds and gates (Phase 5),
and the segment/usage analysis plan. Thresholds are **proposed defaults** for a
Limited Beta; the program lead may tune before launch.

---

## 1. Primary metrics (Phase 3)

| # | Metric | Definition | Instrument | Unit | Beta target | Failure line |
|---|---|---|---|---|---|---|
| M1 | **Time to first recommendation** | Wall-clock: prompt submitted → report produced | Timestamp / form Q11 | minutes | median ≤ 15 min | median > 30 min |
| M2 | **User confidence** | Post: "I trust this as a starting point" (Q10) | Survey | 1–7 | median ≥ 5 | median < 4 |
| M3 | **Recommendation usefulness** | "Useful — I could act on it" (Q5) | Survey | 1–7 | median ≥ 5 | median < 4 |
| M4 | **Clarity** | "Report was clear" (Q6) | Survey | 1–7 | median ≥ 6 | median < 5 |
| M5 | **Traceability** | "Could trace each claim to assumption/evidence" (Q7) | Survey | 1–7 | median ≥ 5 | median < 4 |
| M6 | **Evidence quality** | "Assumptions/evidence acceptable for a draft" (Q8) | Survey | 1–7 | median ≥ 4 | median < 3 |
| M7 | **Editing effort** | Effort to make client-ready (Q15) | Survey (ordinal) | none→rewrite | ≤ "moderate" for ≥70% | "heavy/rewrite" > 40% |
| M8 | **Human override frequency** | Core rec modified or rejected (Q14) | Survey | % engagements | rejected < 20% | rejected > 40% |
| M9 | **Task completion** | Engagement finished end-to-end with a report (Q16) | System + survey | % | ≥ 90% | < 75% |
| M10 | **User satisfaction** | NPS (end survey Q18) | Survey | −100…+100 | ≥ +10 | < −10 |

### Derived / safety metrics
| Metric | Definition | Target |
|---|---|---|
| **Hallucination rate** | Fabricated fact presented as sourced (reviewer-confirmed) | **0 tolerated** on factual claims; any confirmed instance is a release blocker until root-caused |
| **Number-override rate** | Quantitative claims verified/overridden ÷ total (Q13) | Track — informs the Evidence-Provider GA gate |
| **Governance-perceived-value** | "Challenger caught something real" (Q9) | median ≥ 5 (this is the differentiator) |
| **Self-vs-reviewer score gap** | Participant Overall − program reviewer Overall | |gap| ≤ 1.0 (large gap = over-trust risk) |

---

## 2. Acceptance & release gates (Phase 5)

**Acceptance (an engagement "passes"):** completed (M9) **and** usefulness ≥ 5
**and** no confirmed hallucination **and** every load-bearing assumption legible
in the ledger.

**Program release gates (must all hold to consider GA):**
1. ≥ 90 completed engagements across ≥ 4 archetypes and ≥ 4 segments.
2. M3 usefulness median ≥ 5 **and** M2 confidence median ≥ 5.
3. M9 completion ≥ 90%.
4. **Zero** confirmed hallucinations on factual claims (or all root-caused + fixed).
5. Governance-perceived-value median ≥ 5.
6. Number-override rate + qualitative feedback jointly answer: *is a populated
   Evidence Provider a hard GA prerequisite?* (explicit written decision.)

**Failure thresholds (trigger stop/redesign, not GA):** any two primary metrics
below their failure line, **or** completion < 75%, **or** any un-fixable
hallucination pattern, **or** NPS < −10.

---

## 3. Segment analysis (Phase 5)

Break every metric by:
- **User segment** (consultant / strategy team / MBA / founder / analyst) — does
  usefulness hold for non-experts, or only for those who can judge/supply data?
- **Archetype** (the 8) — where is quality strong vs. weak? (Expect soft
  archetypes like org design to score lower, per the eval's C20 = 7.0.)
- **Ambiguity tier** (A1/A2/A3) — does quality degrade as ambiguity rises?
- **Data-supplied vs. assumption-only** (form Q3) — the key question: does
  supplying real data materially raise usefulness/trust? (Tests the empty-vault
  limitation directly.)

Report each cut as median + IQR + n. **Only report a segment when n ≥ 8**;
below that, narrate qualitatively and label "insufficient n." Do **not** compute
confidence intervals on thin cells — the research eval's explicit small-n lesson.

---

## 4. Usage analysis (Phase 5)

- Engagements per participant (distribution); drop-off after engagement 1 (a
  usefulness signal).
- Guided vs. BYO split; completion by type.
- Re-run behavior — did users re-run the same problem (a non-determinism / trust
  signal)? How different were the outputs they reported?
- Time-of-abandonment for incomplete engagements (where in the pipeline it broke).
- Correlation checks (descriptive, not causal): data-supplied ↔ usefulness;
  ambiguity ↔ editing effort; segment ↔ override rate.

---

## 5. Analysis hygiene

- Pre-register these thresholds **before** data collection (this document).
- Two raters per report where feasible; report inter-rater agreement.
- Separate "did the user like it" (satisfaction) from "was it good" (reviewer
  quality) — they can diverge, and the divergence is a finding.
- Publish the raw distributions, not just means; call out worst cases explicitly.
