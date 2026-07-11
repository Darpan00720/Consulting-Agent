# StratAgent — GA Go / No-Go Framework

The decision procedure for whether StratAgent graduates from Limited Beta to
General Availability (v1.0). Decision is made by the Product Evaluation Lead with
Engineering and a Safety/Legal reviewer, against **pre-registered** criteria
([Success Metrics](Success-Metrics.md)).

---

## 1. Decision inputs

1. Beta metrics vs. targets (M1–M10 + safety metrics).
2. All ⛔ blockers on the [Release Checklist](Release-Checklist.md).
3. Qualitative synthesis (strengths, weaknesses, trust, friction).
4. The explicit Evidence-Provider decision (hard prerequisite or ship-with-labeling).

---

## 2. Three-tier decision

### 🟢 GO (ship GA) — all must hold
- Every ⛔ Release-Checklist blocker closed.
- M3 usefulness **and** M2 confidence medians ≥ 5.
- M9 completion ≥ 90%.
- **Zero** unresolved factual hallucinations.
- Governance-perceived-value median ≥ 5.
- ≥ 90 completed engagements across ≥ 4 archetypes and ≥ 4 segments.
- No primary metric below its failure line.
- Safety/Legal sign-off on appropriate-use guardrails.

### 🟡 CONDITIONAL GO (limited/gated GA) — GO criteria mostly met, with named gaps
Ship to a **defined segment or use-band** only, with explicit constraints, when:
- Quality is strong for *some* archetypes/segments but weak for others → GA only
  for the strong ones; weak ones stay "beta / use with caution."
- Evidence Provider not yet populated but human-review guardrails are strong and
  usefulness holds → GA as an explicitly **assumption-labeled drafting tool**,
  not a source of validated numbers.
- Each condition has an owner and a removal date.

### 🔴 NO-GO — any one triggers
- Any ⛔ blocker open.
- A confirmed hallucination pattern that cannot be root-caused/fixed.
- Two or more primary metrics below their failure line.
- Completion < 75%.
- NPS < −10, or override-reject > 40%.
- Safety/Legal withholds sign-off.
→ Route to redesign; re-enter beta after fixes. (Note: architecture is **not**
suspected — RC1.2 resolved the known architectural inconsistencies — so a NO-GO
points at evidence grounding, quality breadth, or safety, not a rebuild.)

---

## 3. Decision matrix (quick reference)

| Condition | GO | Conditional | No-Go |
|---|:--:|:--:|:--:|
| All ⛔ blockers closed | ✓ | ✓ | ✗ → No-Go |
| Usefulness & confidence ≥ 5 | ✓ | partial (segment) | ✗ |
| Completion ≥ 90% | ✓ | ≥ 85% | < 75% |
| Hallucinations | 0 | 0 | pattern unfixable |
| Governance value ≥ 5 | ✓ | ✓ | ✗ |
| Evidence Provider | populated *or* signed-off labeling | labeling-only w/ guardrails | — |
| Safety/Legal sign-off | ✓ | ✓ | ✗ |

---

## 4. Guardrails on the decision

- **Pre-register** thresholds before data collection (done in Success Metrics).
- **Do not move the goalposts** post-hoc; if a threshold was wrong, document the
  change and its rationale explicitly.
- **Worst cases veto averages.** A strong mean does not offset a safety failure or
  an unfixable hallucination pattern.
- **Separate "liked" from "good."** High satisfaction with low reviewer quality =
  over-trust risk → weight toward caution.
- **Small-n honesty.** If a segment/archetype has n < 8, it cannot earn a GO on
  its own; mark "insufficient evidence," not "pass."
- The verdict is **evidence-scoped**: state exactly which segments/archetypes the
  GO covers, and which remain beta.

---

## 5. Output of the review

A one-page decision memo: verdict (🟢/🟡/🔴), the metric table, blockers status,
the Evidence-Provider decision, conditions + owners (if Conditional), and the
scope of the GA claim. Filed alongside this framework.
