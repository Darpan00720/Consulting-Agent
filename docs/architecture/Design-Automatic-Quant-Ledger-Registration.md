# Design: Automatic Quant Ledger Registration (Phases 2–4 of the 2026-07-21 remediation)

**Status: PROPOSED — not implemented.** This is the production-ready design
requested when the calling task's own instructions said: *"If automatic Quant
Ledger registration cannot be implemented safely within the existing
architecture, do NOT introduce a partial solution... produce a production-ready
design... so it can be implemented coherently in a subsequent change."* That
condition is met — see §1 for why a same-night implementation was rejected in
favor of this document.

## 1. Why this isn't implemented tonight

The signed-number bug (Phase 1) was a bounded, reproducible defect in one
regex — fix it, prove it, ship it. Automatic derived-atom registration is a
different kind of change: it would require intercepting and validating
free-form LLM prose *before* it is trusted, for every analyst phase, not just
the final report. Doing that safely needs:

- a way to compute a **derived atom's value independently of ids** (today,
  `ledger_builder._build_block` mints A-n/D-n ids and evaluates formulas in
  one pass, keyed by canonical id — that machinery does not exist yet at
  per-analyst time, before any id has been minted);
- a **rejection-and-rework loop per analyst**, mirroring the report-writer's
  (bounded by `config.MAX_REWORK`), which changes the shape of the analyst
  phase from "one call, cache the result" to "call, validate, possibly retry"
  — a real behavioral change to `engine.py`'s phase() contract, not a prompt
  tweak;
- a decision about **false positives**: an over-eager check that rejects
  legitimate analyst reasoning (e.g. a sentence that merely *mentions* a
  number for comparison, not as a computed claim) would make analysts retry
  indefinitely or silently degrade output quality. The existing `tie_out`
  already has this exact tension at the report-writer stage and resolves it
  with a generous "material number" filter (`_report_numbers`) tuned over
  multiple live-engagement iterations (2026-07-16, 2026-07-19, 2026-07-21) —
  a NEW analyst-level filter would need the same tuning, and one on-paper
  design pass cannot know the right calibration without running it against
  real cases.

Implementing this in the same session as the Phase 1 fix would have meant
either (a) rushing a naive check with no calibration history, risking either
too many false-positive reworks (burning the free-tier provider quota) or too
many false negatives (defeating the purpose), or (b) claiming "automatic
registration" while actually shipping something narrower. Neither is honest
engineering. This document is the alternative: a concrete plan a future
session can implement and calibrate deliberately.

## 2. What already exists (do not rebuild)

- `evidence_schema.py` — analyst-level atom schema (`fact`/`assumption`/
  `derived`/`unknown`), already enforces "a derived atom carries only a
  formula, never a value" at the individual-analyst level.
- `evidence_normalizer.py` / `evidence_store.py` — dedup, conflict detection,
  and serialization of one engagement's aggregated atoms.
- `ledger_builder.py` — the ONLY place derived values are actually computed
  (id minting, dependency-ordered evaluation, exact `Decimal` arithmetic).
  This runs once, on the Engagement Manager's reconciliation, not per-analyst.
- `quantcheck.tie_out` — the existing report-vs-ledger reconciliation check,
  now sign-correct (Phase 1 of this remediation).
- `quantcheck.unresolved_unknowns` — the Recommendation Gate backstop added
  in the immediately-prior remediation pass.

The gap is specifically: **nothing runs equivalent id-minting-and-evaluation
logic on an individual analyst's atoms before the Engagement Manager sees
them**, so an analyst can state a computed figure in prose that never became
even an unresolved atom — it's simply prose, invisible to every check above
until the *report* is written and `tie_out` catches it, several phases later.

## 3. Proposed architecture

### 3.1 New component: `analyst_ledger.py`

A lightweight sibling to `ledger_builder.py`, scoped to ONE analyst's already-
parsed `EvidenceAtom` list (from `evidence_schema.parse_evidence_block`,
already running per-analyst at `engine.py:795`). Unlike `ledger_builder`, it
does not mint canonical A-n/D-n ids (those don't exist until the EM reconciles
across analysts) — it only needs to **evaluate each analyst's own `derived`
atoms locally**, keyed by their own `atom_id` (already unique within one
analyst's block, per `evidence_schema.py`'s existing duplicate-id check), so
their computed values exist as real numbers to reconcile the analyst's OWN
prose against.

```python
def evaluate_analyst_atoms(atoms: tuple[EvidenceAtom, ...]) -> dict[str, Decimal]:
    """Compute every derived atom's value from this analyst's own facts/
    assumptions, keyed by atom_id. Reuses quantcheck._eval/_parse_formula —
    the same trusted arithmetic ledger_builder already uses, just addressed
    by atom_id instead of a minted canonical id (no ids exist yet)."""
```

### 3.2 New check: `quantcheck.analyst_tie_out`

A variant of `tie_out` that accepts `{atom_id: Decimal}` directly (no `Entry`
wrapping needed — units/anchors/bridges are EM-reconciliation concerns, not
per-analyst ones) and checks the analyst's raw markdown against: its own atom
values, the case prompt, and — critically — **nothing else**, since an
analyst cannot legitimately cite another analyst's figures yet (that's the
EM's reconciliation job). This asymmetry (stricter than `tie_out`, which also
allows any ledger value) is deliberate: it should catch "I computed a number
and never told the atom schema" specifically, not "I cited someone else's
number early."

### 3.3 Wiring into `engine.py`

Immediately after each analyst's evidence block is parsed (today:
`engine.py:795-802`), before that analyst's output is cached:

```
parsed = evidence_schema.parse_evidence_block(analyst_outputs[agent], agent)
if not parsed.errors:
    values = analyst_ledger.evaluate_analyst_atoms(parsed.atoms)
    check = quantcheck.analyst_tie_out(analyst_outputs[agent], values, case_prompt)
    if not check.passed and rework_budget_left:
        # bounded retry, mirroring the report-writer's tie_out loop
        analyst_outputs[agent] = await phase(..., defect list, ...)
```

This is the SAME shape as the report-writer's already-shipped rework loop
(this remediation's Phase-6 change) — reusing a pattern already proven live,
not inventing a new control-flow shape.

## 4. Migration steps

1. Build `analyst_ledger.py` + `quantcheck.analyst_tie_out` in isolation, with
   unit tests against synthetic analyst atom lists — no engine.py change yet.
2. Run it **in shadow mode** first: call it after each analyst phase, log
   defects via telemetry, but do NOT rework or block anything. Collect data
   across a batch of real (or replayed) engagements to calibrate the
   "material number" filter for analyst prose specifically — analyst working
   notes read differently from a polished report (more hedged, more
   comparison-heavy), so `_report_numbers`'s existing tuning cannot be
   assumed to transfer unchanged.
3. Once shadow-mode false-positive rate is acceptably low (a number to set
   deliberately, not guess — suggest starting the bar at "zero false
   positives across N replayed real engagements" before flipping the gate
   live), wire the rework loop for real, bounded by a NEW config knob
   (`STRATAGENT_ANALYST_MAX_REWORK`, default 1, independent of the existing
   `MAX_REWORK` so the two can be tuned separately).
4. Only after that: revisit whether `unresolved_unknowns` and the report-
   writer's `tie_out` can be *narrowed* now that most violations are caught
   upstream — but keep both regardless, since defense in depth is exactly
   this platform's existing philosophy (the EM reconciliation gate and the
   report tie-out already both exist for the same reason: catching a defect
   introduced at ANY later stage, not trusting an earlier stage's cleanliness).

## 5. Risks

- **False-positive reworks burn free-tier provider quota** faster than
  today, since a new gate fires once per analyst (5×) instead of once per
  report. Mitigate via the shadow-mode step above before ever blocking.
- **An analyst legitimately needs to reference a case-prompt number in a
  derived expression it never registers as its own atom** (e.g. quoting a
  competitor's public multiple for comparison, not as a load-bearing
  calculation) — `analyst_tie_out` must distinguish "stating a fact for
  color" from "computing a claim," which `_report_numbers`'s existing
  currency/percent/comma filter does today for reports; it is not proven yet
  for analyst prose specifically.
- **This still does not make violation "impossible by construction"** — it
  narrows the window from "caught at final report" to "caught after this
  analyst's phase," which is a real, valuable improvement, but an analyst
  rework could itself introduce a NEW uncaught inline number the retry
  prompt doesn't anticipate. True impossibility would require structured,
  atom-only analyst output with no free-form numeric prose at all — a much
  larger product change (analysts would no longer write natural analytical
  prose) that is out of scope for this design and would need its own product
  discussion, not an engineering decision alone.
