---
adr: 011
title: Consulting Quality Roadmap — closing the gap to MBB Partner-grade output
status: Proposed (design only — no implementation started)
date: 2026-07-18
deciders: [Principal Architect / Engagement Partner]
relates: [ADR-005 Agent Specifications, ADR-006 Governance and Live Validation, ADR-009 Deterministic Quant Gate, ADR-010 Consulting Operating System, ADR-014 Consulting Architecture Convergence]
supersedes: []
tags: [consulting-methodology, governance, quality, roadmap]
---

# ADR-011 — Consulting Quality Roadmap

> **Status:** This is a design document, not an implementation record. It
> follows two audits performed this session — an architecture/engineering
> audit and a management-consulting-methodology audit (a Partner-level review
> of executive reasoning, business judgment, executive communication,
> methodology, quality assurance, and client trust, grounded in the real
> agent prompts and real generated sample-engagement reports under
> `engagements/`). Findings from both audits are assumed accepted here, not
> restated — this document is the roadmap to close them. Nothing in this
> document authorizes implementation; each phase requires its own go-ahead,
> consistent with this project's standing design-first rule.

> **2026-07-19 note (added by the ADR-014 documentation consistency
> audit):** Workstream H (Knowledge Management) and K (Framework
> Improvements) below govern `knowledge-vault/*.md` and
> `packages/knowledge/retrieval_adapter.py` — the Claude Code plugin's
> prose knowledge base. A separate, typed Python framework catalog
> (`app.knowledge`, informally "W8") and organization/RACI model
> (`app.organization`, "W9") also exist in `apps/dashboard/backend`,
> governed by ADR-014. These are **different artifacts serving different
> consumers** (this roadmap's knowledge-vault vs. `app.pipeline`'s
> deterministic selection logic); integrating W8/W9 per ADR-014 does not
> close any item in this document, and closing an item here does not
> require touching W8/W9. Do not conflate the two when planning work
> against either document.

---

## 1. Why this roadmap exists

The consulting audit's headline finding: StratAgent's prompt engineering
shows real consulting literacy (Pyramid Principle and SCQA are explicitly
instructed; sensitivity analysis is properly tied to decision-flip points;
second-order effects are required in places) — but the system is
**fact-checked, not judgment-checked**. Every quality gate verifies that
numbers are traceable and internally consistent. Almost none of them verify
that the thinking is any good. And the knowledge base underneath every
recommendation is self-labeled, in its own files, as never having been
reviewed by a human.

This roadmap closes that gap in ordered phases, organized into fourteen
workstreams. 48 items total. Each item states what it is, why it matters,
what it improves, how much it costs, what it depends on, what it touches,
and how urgent it is.

---

## 2. Workstreams

### A. Consulting Methodology

**A1 — Root-Cause Hypothesis Generation Step**
- *Objective:* Insert an explicit step (new agent or extended case-classifier
  output) that generates 2–4 ranked root-cause hypotheses — with rationale
  and the evidence that would disconfirm each — before framework selection.
- *Why it matters:* `case-classifier.md:37-39` today only reframes the
  client's symptom into a decision question ("profit is down" → "exit or
  fix the region?"). It never asks *why* profit is down. Real case teams
  hypothesize cause before they hypothesize action.
- *Expected improvement:* the engagement starts with a causal theory, not
  just a decision framing — the actual entry point of hypothesis-driven
  consulting.
- *Effort:* Medium.
- *Dependencies:* None. Feeds A2, B2.
- *Files:* `plugins/ruflo-stratagent/agents/case-classifier.md` (or a new
  `root-cause-hypothesis.md` agent), `skills/solve-case/SKILL.md`,
  `consulting_schema.py` (new `RootCauseHypothesis` type).
- *Priority:* **Critical.**

**A2 — Hypothesis-Driven Issue Tree Enforcement**
- *Objective:* Require every issue-tree leaf to carry a stated, falsifiable
  hypothesis string — not just a question — validated as non-empty and
  distinct from the question text.
- *Why it matters:* the knowledge vault's own template already demands this
  (`knowledge-vault/issue-trees/profitability.md:40`: "Each leaf states a
  falsifiable hypothesis") but the real generated output doesn't meet it —
  `engagements/northwind-eu-entry/03-issue-tree.md` produces decision-
  threshold questions, not hypotheses. `mece_validator.py` checks tree shape
  only (no cycles, leaf ownership, no duplicate questions), never content.
- *Expected improvement:* trees become prove-the-answer structures instead
  of exhaustive descriptive maps — faster convergence, closes a gap between
  the system's own documented standard and its actual output.
- *Effort:* Low–Medium.
- *Dependencies:* A1 (ideally feeds branch structure).
- *Files:* `plugins/ruflo-stratagent/agents/issue-tree-generator.md`,
  `packages/planning/mece_validator.py`, `consulting_schema.py` (`IssueNode`).
- *Priority:* **Critical.**

**A3 — Value-of-Information Work Sequencing**
- *Objective:* Planner sequences analyst dispatch by which question, if
  answered, eliminates the most branches / has the highest expected impact
  on the recommendation — not just topological dependency.
- *Why it matters:* `planner.md:65-70` sequences purely by dependency today
  (confirmed against real output in `engagements/northwind-eu-entry/02-plan.md`).
  Real MBB fieldwork tests the hypothesis most likely to kill the case
  first.
- *Expected improvement:* faster convergence to a defensible answer; a
  secondary token-cost benefit (less analysis spent on low-leverage
  branches).
- *Effort:* Medium.
- *Dependencies:* A1, A2.
- *Files:* `plugins/ruflo-stratagent/agents/planner.md`.
- *Priority:* High.

**A4 — Missing Framework Notes (root-cause, hypothesis-tree, SCQA, Pyramid,
prioritization)**
- *Objective:* Add first-class knowledge-vault framework files for: 5 Whys /
  fishbone root-cause analysis, hypothesis-tree (distinct from generic issue
  tree), SCQA, Pyramid Principle, and impact/effort or ICE/RICE
  prioritization.
- *Why it matters:* zero grep hits for any of these across all 63 framework
  files. SCQA/Pyramid currently live only inside `report-writer.md`'s own
  prompt — no other agent (issue-tree-generator, case-classifier) can draw
  on them as taught methodology.
- *Expected improvement:* consistent methodology across agents instead of
  siloed in one prompt.
- *Effort:* Low (content authoring, ~60 lines per note, matching existing
  template).
- *Dependencies:* None.
- *Files:* `knowledge-vault/frameworks/five-whys.md`,
  `hypothesis-tree.md`, `scqa.md`, `pyramid-principle.md`,
  `ice-rice-prioritization.md`, `impact-effort-matrix.md`.
- *Priority:* High.

**A5 — Populate `when_not_to_use` on Framework Notes**
- *Objective:* Populate the `when_not_to_use` field that `framework-
  selector.md:63-67` is already instructed to check.
- *Why it matters:* a grep across all 63 framework files finds this field
  **nowhere** — the selector's Step 3 check is a structurally guaranteed
  no-op today.
- *Expected improvement:* fewer forced-fit framework applications; makes the
  system's own "frameworks are tools, not scripts" design principle
  actually enforceable.
- *Effort:* Low–Medium (start with the ~15 most-frequently-selected
  frameworks, then the remaining 48).
- *Dependencies:* None.
- *Files:* `knowledge-vault/frameworks/*.md`,
  `packages/knowledge/frontmatter.py` (confirm schema field exists).
- *Priority:* High.

---

### B. Executive Reasoning

**B1 — Observation / Implication / Recommendation Schema Separation**
- *Objective:* Extend the finding/evidence schema with three distinct
  fields — fact, implication ("so what"), and linkage to the eventual
  recommendation — instead of one blended prose paragraph.
- *Why it matters:* `report-writer.md:70-84`'s template blends evidence,
  assumption-labeling, and the "so what" into a single 2–4 sentence block.
  This is exactly the distinction a reviewing partner uses to test a
  junior's thinking; blending it makes any one layer hard to challenge
  independently.
- *Expected improvement:* reviewable, challengeable arguments layer by
  layer; direct input to D2 (conclusion reconciliation) and F2 (argument
  survivability check).
- *Effort:* Medium (schema change; all 5 analyst prompts updated to emit
  the 3 fields; report-writer renders from them instead of free prose).
- *Dependencies:* Coordinate with the existing structured-evidence platform
  (ADR-010 §6a) rather than duplicating it.
- *Files:* `apps/dashboard/backend/app/pipeline/consulting_schema.py`,
  `evidence_schema.py`, all analyst `.md` files, `report-writer.md`.
- *Priority:* **Critical.**

**B2 — Root-Cause Traceability in Findings**
- *Objective:* Each analyst finding states which root-cause hypothesis (A1)
  it supports or refutes.
- *Why it matters:* without this link, causal reasoning gets lost between
  case framing and analyst output even once A1 exists.
- *Expected improvement:* end-to-end causal traceability from hypothesis →
  evidence → recommendation.
- *Effort:* Medium.
- *Dependencies:* A1, B1.
- *Files:* analyst `.md` files, `consulting_schema.py`.
- *Priority:* High.

**B3 — Reviewer "So-What" Check (new RC-6)**
- *Objective:* New reviewer criterion checking that every finding's
  implication field is non-trivial — not a restatement of the observation.
- *Why it matters:* moves at least one reviewer check from purely structural
  toward substantive.
- *Expected improvement:* catches "so what" gaps automatically instead of
  relying on the report-writer to notice.
- *Effort:* Low (new RC criterion; still LLM judgment, but explicitly
  specified rather than absent).
- *Dependencies:* B1.
- *Files:* `plugins/ruflo-stratagent/agents/reviewer.md`.
- *Priority:* Medium.

---

### C. Business Judgment

**C1 — Mandatory "Cost of Inaction" Baseline**
- *Objective:* Every recommendation is accompanied by an explicit
  quantified (or clearly-bounded qualitative) cost-of-inaction / do-nothing
  comparison.
- *Why it matters:* zero hits for "cost of inaction," "counterfactual," or
  "status quo baseline" across every agent prompt. "Do nothing" appears only
  as one *optional* candidate option in `strategy-analyst.md:50-53`'s
  example lists, never a mandatory baseline. This was the audit's #4 reason
  a Partner would refuse to send the output to a client.
- *Expected improvement:* every recommendation is now benchmarked against
  the real counterfactual, not an implicit one.
- *Effort:* Medium.
- *Dependencies:* None.
- *Files:* `financial-analyst.md`, `strategy-analyst.md`, `report-writer.md`,
  `consulting_schema.py` (`cost_of_inaction` field on `Recommendation`).
- *Priority:* **Critical.**

**C2 — Mandatory Quantified Counter-Scenario in Challenger**
- *Objective:* CC-2 ("strongest counter-case") must produce a quantified
  alternative number/scenario, not just a qualitative objection; the
  Challenger explicitly re-tests the recommendation against financial-
  analyst's own bear case.
- *Why it matters:* all six of Challenger's checks (`challenger.md:39-79`)
  are qualitative pass/fail judgments today; none produces a competing
  number or forces a re-run against a non-base scenario. Audit reason #8.
- *Expected improvement:* pressure-testing becomes a real red-team exercise
  with numbers, not just an argument.
- *Effort:* Medium (challenger already has read access to financial-
  analyst's scenario table via context).
- *Dependencies:* None.
- *Files:* `plugins/ruflo-stratagent/agents/challenger.md`.
- *Priority:* **Critical.**

**C3 — Implementation Feasibility as a Mandatory Scoring Dimension**
- *Objective:* Strategy-analyst scores "organizational readiness / execution
  risk" for every option as a required dimension, not an optional example
  weight.
- *Why it matters:* `strategy-analyst.md:59` lists "integration complexity"
  as one item in an *example* weighting scheme only. Strategically-correct-
  but-unexecutable recommendations are what a skeptical COO attacks first.
- *Expected improvement:* recommendations pre-screened for organizational
  executability, not just strategic logic.
- *Effort:* Low–Medium.
- *Dependencies:* None. Feeds D3.
- *Files:* `strategy-analyst.md`,
  `apps/dashboard/backend/app/pipeline/recommendation_ranker.py`.
- *Priority:* High.

**C4 — Dimension-by-Dimension Trade-off Table**
- *Objective:* Strategy-analyst outputs an explicit "Option A wins on X,
  loses on Y" comparison table across a shared dimension set, in addition
  to the weighted scorecard.
- *Why it matters:* current output is a single composite score plus a
  runner-up rationale paragraph — insufficient for a board that wants to
  see the actual trade being made, not just the winner.
- *Effort:* Low.
- *Dependencies:* C3.
- *Files:* `strategy-analyst.md`, `report-writer.md`.
- *Priority:* Medium.

**C5 — Second-Order Effects Parity for Financial-Analyst**
- *Objective:* Bring financial-analyst up to operations-analyst's existing
  standard (`operations-analyst.md:27-29,49-50`: "never recommend a cost
  cut without stating what capability or revenue risk it trades off").
- *Why it matters:* financial-analyst currently has no equivalent
  instruction — financial recommendations (price increases, cost cuts) have
  revenue-side and behavioral second-order effects a pure model misses.
- *Effort:* Low (mirror the existing operations-analyst language).
- *Dependencies:* None.
- *Files:* `financial-analyst.md`.
- *Priority:* Medium.

**C6 — Named Owner + Hard Due Date on Risk Mitigations**
- *Objective:* Extend the risk register from function-level owner ("Legal")
  to named role + explicit date/milestone.
- *Why it matters:* a mitigation with a function but no date is an
  observation, not an action plan (`risk-analyst.md:55` register has no
  date field).
- *Effort:* Low.
- *Dependencies:* None.
- *Files:* `risk-analyst.md`.
- *Priority:* Medium.

**C7 — Ramp-Up / Capacity Realism Checklist**
- *Objective:* Operations-analyst explicitly addresses hiring lead time,
  change-management load, and current capacity constraint against its own
  recommendation, replacing the single unelaborated "effort/time" field.
- *Why it matters:* instantaneous-implementation assumptions get caught
  immediately by any experienced operator reading the report.
- *Effort:* Low–Medium.
- *Dependencies:* None.
- *Files:* `operations-analyst.md`.
- *Priority:* Medium.

---

### D. Recommendation Quality

**D1 — Recommendation "Kill" Verdict**
- *Objective:* Add a fourth Challenger verdict — `reject` (the honest answer
  is: don't pursue this) — distinct from `needs_rework`.
- *Why it matters:* today's three verdicts (`stands` / `stands_with_caveats`
  / `needs_rework`, `challenger.md:90-93`) have no terminal "this is a bad
  idea" state — every path either ships or silently escalates after three
  rework loops. Audit reason #5, and arguably the single highest-leverage
  governance change in this roadmap.
- *Expected improvement:* the platform can produce "we recommend against
  the transformation as scoped" as a valid, trusted output — a real
  credibility-building capability, not a failure mode.
- *Effort:* Medium (verdict schema change; report-writer must handle a
  `reject` path — produce a "why this doesn't work + what would need to be
  true" memo instead of a recommendation; orchestration must route on it).
- *Dependencies:* None, but touches orchestration.
- *Files:* `challenger.md`, `report-writer.md`,
  `apps/dashboard/backend/app/pipeline/engine.py` (`_challenger_verdict`),
  `packages/governance/gates.py`.
- *Priority:* **Critical.**

**D2 — Strategic-Conclusion Reconciliation Gate**
- *Objective:* New check (reviewer RC-6 or a dedicated step) that detects
  when two analysts' *conclusions* conflict (e.g., market-analyst "enter"
  vs. risk-analyst "prohibitive risk") — not just conflicting numbers — and
  forces the report-writer to visibly adjudicate rather than silently
  blend them.
- *Why it matters:* today's only cross-analyst check, `reviewer.md`'s RC-3,
  catches numeric contradiction only; `report-writer.md:76-77`'s
  reconciliation instruction is explicitly for a "canonical reconciliation
  figure" — numeric, not strategic. Audit reason #6.
- *Expected improvement:* visible, resolved tension instead of hidden
  disagreement — one of the fastest ways a board loses trust once noticed.
- *Effort:* Medium–High (each analyst needs to emit a structured "conclusion
  polarity" on the core question, then a comparison step).
- *Dependencies:* B1.
- *Files:* `reviewer.md`, `report-writer.md`, `consulting_validators.py`,
  all analyst `.md` files.
- *Priority:* **Critical.**

**D3 — Recommendation Ranker Live-Wiring**
- *Objective:* Finish wiring the already-built, already-tested
  `recommendation_ranker.py` (ADR-010 §6b — "built and tested but not
  wired") into the live strategy-analyst → report-writer path, so the final
  ranking is a real deterministic computation, not the LLM's own claimed
  order.
- *Why it matters:* this is a self-documented gap, not a new finding — the
  deterministic ranker already exists and already rejects weak options
  below a stated floor; it's just not in the live path.
- *Effort:* Medium (prompt rewrite so strategy-analyst emits the ranker's
  expected input shape; wire the ranker call into `engine.py`).
- *Dependencies:* Should sequence after C3/C4, since those change the
  scoring dimensions the ranker consumes.
- *Files:* `strategy-analyst.md`, `recommendation_ranker.py`, `engine.py`.
- *Priority:* High.

**D4 — Confidence-vs-Reality Backtest Field**
- *Objective:* Where a past engagement's actual outcome later becomes known,
  tag the original recommendation's stated confidence against the realized
  outcome.
- *Why it matters:* "Medium confidence" should mean something empirically
  over time, not just be a hedge word.
- *Effort:* High (depends on an outcome-capture mechanism that doesn't
  exist yet).
- *Dependencies:* I2 (outcome feedback loop).
- *Files:* new module, e.g. `apps/dashboard/backend/app/pipeline/calibration.py`.
- *Priority:* Low (long-horizon).

---

### E. Executive Communication

**E1 — Overall Confidence as a Hard Schema Gate**
- *Objective:* Make `confidence.overall` a required, validated field before
  a report can be marked complete — the same treatment the Quant Gate gives
  numeric ledgers.
- *Why it matters:* `report-writer.md:212-220` already mandates this field,
  but `engagements/halberd-cost/report.md:35` states it while
  `engagements/northwind-eu-entry/state.json`'s `confidence` field is
  **null** — an already-identified compliance gap. Audit reason #7.
- *Expected improvement:* guaranteed consistent confidence reporting across
  every engagement — cheap fix, high visibility.
- *Effort:* Low.
- *Dependencies:* None.
- *Files:* `reporting/validation.py` (or live-path equivalent),
  `scripts/validate_engagement.py`.
- *Priority:* **Critical** (cheap, high-visibility, ship first).

**E2 — Audience-Adaptive Reporting**
- *Objective:* Add an audience parameter (Board / CEO / CFO / Operating
  Committee) that changes section ordering, depth, and opening framing —
  not full content regeneration.
- *Why it matters:* zero matches for "audience," "CFO," "CEO," or "tone" in
  `report-writer.md`; one fixed structure regardless of reader today.
- *Effort:* Medium.
- *Dependencies:* None.
- *Files:* `report-writer.md`, `case-classifier.md` (capture intended
  audience), `SKILL.md`.
- *Priority:* Medium.

**E3 — Hedge-Stack Detector**
- *Objective:* Automated check flagging any sub-claim with 2+ stacked
  conditionals sitting under a governing recommendation that itself claims
  "no hedging."
- *Why it matters:* observed directly in the real northwind report —
  `report.md:9` opens "no hedging," `report.md:75` reads "marginally favors
  direct... holding only at the optimistic end (build ≤9 months *and* no
  re-architecture *and* the hyperscaler doesn't accelerate)." This exact
  pattern is what erodes trust fastest.
- *Effort:* Low–Medium (deterministic text-pattern check + a reviewer
  addition).
- *Dependencies:* B1 (structured findings make per-claim checking easier).
- *Files:* new `report_lint.py`, `reviewer.md`.
- *Priority:* Medium.

**E4 — Redundancy / Repetition Check**
- *Objective:* Flag claims restated near-verbatim across 2+ sections.
- *Why it matters:* northwind's real report repeats the same EU-vs-APAC
  NPV-tie point three times (exec summary, branch B, risks) — 2,706 words
  vs. halberd's disciplined 762 for a comparable deliverable.
- *Effort:* Low.
- *Dependencies:* None.
- *Files:* `report_lint.py` (shared with E3), `report-writer.md`.
- *Priority:* Medium.

**E5 — Enforce Existing Word Caps as a Hard Gate**
- *Objective:* Make the prompt's already-stated section word caps (e.g.
  Executive Brief ≤250 words, `report-writer.md:204-206`) a validated gate
  instead of aspirational prose.
- *Effort:* Low.
- *Dependencies:* E4 (shares the lint module).
- *Files:* `report_lint.py`, `scripts/validate_engagement.py`.
- *Priority:* Medium.

**E6 — Render Observation/Implication/Recommendation Structure in the
Report Template**
- *Objective:* Once B1's schema exists, carry the structural separation
  through to the reader-facing document — a consistent "what we found → what
  it means → what we recommend" micro-structure per section.
- *Effort:* Low (template change once B1 exists).
- *Dependencies:* B1.
- *Files:* `report-writer.md`.
- *Priority:* Medium.

---

### F. Quality Assurance

**F1 — Knowledge-Base Review & Promotion Pipeline**
- *Objective:* A real human-review workflow promoting framework/industry
  notes from `draft` to `approved`; framework-selector/report-writer prefer
  (or, above a materiality threshold, require) `approved` content.
- *Why it matters:* every one of the 63 framework files and 10 industry
  files checked carries the identical footer "Draft (AI-authored,
  unreviewed). Promote to `approved` only after reviewer sign-off." This is
  the single most consequential finding of the whole audit — audit reason
  #1.
- *Expected improvement:* every material claim in a client report traces to
  human-reviewed methodology, not just LLM-authored-and-never-checked
  content.
- *Effort:* High (this is a standing operational commitment — someone has
  to actually review the content — not just a code change).
- *Dependencies:* None technically; pairs with F4 (tiering) for
  enforcement scope.
- *Files:* `knowledge-vault/frameworks/*.md`, `knowledge-vault/industries/*.md`
  (status field), `plugins/ruflo-stratagent/agents/knowledge-curator.md`
  (extend its existing remit), `framework-selector.md`.
- *Priority:* **Critical.**

**F2 — Reviewer "Argument Survivability" Check (RC-6, or RC-7 if paired
with B3)**
- *Objective:* New reviewer criterion explicitly modeling a skeptical-CFO
  pressure test: does each major claim state a counter-argument it already
  addresses?
- *Why it matters:* "would this survive a skeptical CFO's questioning"
  appears nowhere in `reviewer.md` today; all five existing RC-criteria are
  structural/mechanical.
- *Effort:* Medium (inherently an LLM-judgment check, but a concretely
  specified one).
- *Dependencies:* C2 (Challenger's quantified counter-scenario) is good
  input material.
- *Files:* `reviewer.md`.
- *Priority:* High.

**F3 — Independent Model Verification for Governance Gates**
- *Objective:* Route Reviewer and/or Challenger through a structurally
  different model (per ADR-010 §6d's designed-not-live Gemini tie-breaker
  role, or at minimum a different provider in the existing multi-provider
  chain) for any engagement above a materiality threshold.
- *Why it matters:* every agent, including Reviewer and Challenger,
  declares `model: inherit` — the identical model as the analysts being
  checked, differentiated only by prompt. The entire governance-gate story
  currently runs on correlated-failure risk, not structural independence.
- *Expected improvement:* genuine second-opinion verification for
  high-stakes engagements, not persona-switching on the same model.
- *Effort:* Medium–High (routing-policy change; the multi-provider chain
  already exists, so this is largely policy, not new infrastructure).
- *Dependencies:* ADR-010 §6d's model-governance framework.
- *Files:* `apps/dashboard/backend/app/pipeline/providers.py`, `engine.py`.
- *Priority:* **Critical.**

**F4 — Materiality-Tiered Engagement Rigor**
- *Objective:* Define explicit tiers (e.g., "advisory sketch" vs.
  "board-ready deliverable") with different mandatory gate sets. Board-ready
  requires F1 (approved sources only), F3 (independent verification), G1
  (human sign-off), and the full quality bar; lighter tiers can skip some
  for speed.
- *Why it matters:* without tiering, either everything is under-governed or
  everything is prohibitively slow/expensive for internal/exploratory use.
- *Effort:* Medium.
- *Dependencies:* F1, F3, G1.
- *Files:* `case-classifier.md` (capture intended tier), `config.py`,
  `validate_engagement.py`.
- *Priority:* High.

**F5 — Extend Quant Gate Tie-Out to Qualitative Claims**
- *Objective:* Extend the existing tie-out check (ADR-009) so qualitative
  language ("significant," "material") must have a numeric claim backing it
  somewhere in the ledger, not just numbers matching numbers.
- *Effort:* Medium.
- *Dependencies:* existing `quantcheck.py` `tie_out` function.
- *Files:* `apps/dashboard/backend/app/pipeline/quantcheck.py`.
- *Priority:* Low–Medium.

---

### G. Client Trust / Risk & Governance

**G1 — Mandatory Human Sign-Off Gate Before Delivery**
- *Objective:* For any engagement at the "board-ready" tier (F4), require
  explicit human approval before a report is marked deliverable — a
  structural gate, not the current fallback-after-3-failures escalation.
- *Why it matters:* no real consulting deliverable reaches a Fortune 500
  board without partner sign-off; today's pipeline can run fully
  autonomously end to end. This is also the change most likely to make the
  platform sellable as a partner-augmentation tool rather than an
  unsupervised report generator.
- *Effort:* Medium (a `pending_human_approval` terminal state; an approval
  UI affordance in the dashboard).
- *Dependencies:* F4.
- *Files:* `engine.py`, dashboard frontend (approval UI), `SKILL.md`.
- *Priority:* **Critical.**

**G2 — Board Simulation (persona panel pressure test)**
- *Objective:* Implement ADR-010's already-scoped G4/P5: a CEO/CFO/COO/CIO/
  CHRO/Chair/Investor/Audit persona panel that pressure-tests the
  recommendation for approvability, distinct from and in addition to the
  Challenger.
- *Why it matters:* real board presentations get contested from multiple,
  role-specific angles simultaneously (an investor's capital-efficiency
  objection is not a CHRO's change-fatigue objection) — a single
  adversarial pass doesn't replicate that.
- *Expected improvement:* pre-empts the most likely real objections before
  the actual board meeting; genuinely differentiating capability.
- *Effort:* High (new persona agent(s), new orchestration phase, synthesis
  logic reconciling persona objections into an "anticipated objections and
  pre-built responses" appendix).
- *Dependencies:* D1 (kill verdict), D2 (reconciliation gate) — board sim
  should be able to trigger the same paths.
- *Files:* new agent(s) under `plugins/ruflo-stratagent/agents/`, `SKILL.md`,
  `report-writer.md` (new "Anticipated Board Questions" section).
- *Priority:* High (large, genuinely differentiating — not required for the
  boutique bar; see §3).

**G3 — Regulatory/Legal Escalation for High-Stakes Domains**
- *Objective:* Explicit flag requiring human legal/compliance sign-off when
  a case touches specifically regulated domains (M&A antitrust, healthcare,
  financial services, data privacy) — stronger than risk-analyst's current
  generic mention.
- *Effort:* Medium (domain-detection flag from case-classifier + a hard
  block in the delivery gate absent human legal sign-off).
- *Dependencies:* G1.
- *Files:* `case-classifier.md`, `validate_engagement.py`.
- *Priority:* High.

**G4 — Stronger Provenance Standard for Client Facts (board-ready tier)**
- *Objective:* Where evidence type is `client_fact` (vs. benchmark/analyst-
  estimate), require a stronger provenance standard — a specific document/
  interview/data-room reference, not just a free-text label — before it can
  be load-bearing at the board-ready tier.
- *Why it matters:* `source_reference` is currently unchecked free text; an
  LLM can cite a fabricated source and it passes schema validation as long
  as the category label is valid.
- *Effort:* Medium (schema tightening scoped to the F4 board-ready tier
  only; lighter tiers keep current flexibility).
- *Dependencies:* F4.
- *Files:* `evidence_schema.py`.
- *Priority:* High.

---

### H. Knowledge Management

**H1 — Semantic/Embedding-Based Retrieval**
- *Objective:* Replace or augment the current weighted-keyword scorer with
  real semantic (embedding) retrieval.
- *Why it matters:* current retrieval (`packages/knowledge/retrieval_adapter.py`)
  is a pure lexical field-weighted match — not TF-IDF, not semantic — with
  no relevance floor above zero. A note matching one incidental word can
  score as a "hit," contaminating an analyst's evidence context.
- *Effort:* Medium–High (embeddings for 133 notes, a vector index, a
  minimum-relevance floor; preserve existing field-weighting as a
  re-ranking signal rather than discarding it).
- *Dependencies:* None.
- *Files:* `packages/knowledge/retrieval_adapter.py`, new embeddings module.
- *Priority:* High.

**H2 — Staleness/Currency Enforcement**
- *Objective:* Surface note age to the consuming analyst; require
  justification if a note older than N years is load-bearing for a
  fast-moving domain (market data, regulation, competitive dynamics).
- *Why it matters:* `last_verified` is currently only a tie-breaker in
  retrieval ranking, never a filter or a surfaced flag.
- *Effort:* Low–Medium.
- *Dependencies:* None.
- *Files:* `retrieval_adapter.py`, `frontmatter.py`.
- *Priority:* Medium.

**H3 — Industry Benchmark Population**
- *Objective:* Populate actual numeric benchmark ranges into industry files
  or a companion KPI-benchmark dataset.
- *Why it matters:* `knowledge-vault/industries/retail.md:32-33` states
  outright that benchmarks are "reviewer-supplied" — the numbers a real
  industry-context claim needs simply aren't in the system today.
- *Effort:* High (real research/content work, with citations).
- *Dependencies:* F1 (route through the same review/approval pipeline).
- *Files:* `knowledge-vault/kpis/*.md`, `knowledge-vault/industries/*.md`.
- *Priority:* High.

**H4 — Framework Combination Guidance**
- *Objective:* An explicit meta-guide on which framework pairs are commonly
  and legitimately combined vs. which combinations double-count.
- *Effort:* Low–Medium.
- *Dependencies:* A5.
- *Files:* `knowledge-vault/frameworks/_meta/combination-guide.md`,
  `framework-selector.md`.
- *Priority:* Low–Medium.

**H5 — Non-English / Non-US Market Coverage**
- *Objective:* Localization-aware knowledge notes and explicit agent
  instructions for non-US regulatory/market/cultural context.
- *Why it matters:* no localization/translation handling exists anywhere in
  the agent prompts today.
- *Effort:* High (real content + prompt work per target market — scope to
  2–3 markets, e.g. EU given the northwind sample engagement, not "all
  markets" from day one).
- *Dependencies:* None.
- *Files:* new `knowledge-vault/markets/` directory, `market-analyst.md`.
- *Priority:* Medium.

**H6 — Multi-Stakeholder Conflicting-Objectives Modeling**
- *Objective:* Explicit handling for cases where internal stakeholders have
  genuinely conflicting objectives (growth vs. margin, HQ vs. regional
  autonomy) as a distinct analysis dimension, not assumed away.
- *Effort:* Medium.
- *Dependencies:* None.
- *Files:* `case-classifier.md`, `information-gap.md`, `report-writer.md`.
- *Priority:* Medium.

---

### I. Learning & Continuous Improvement

**I1 — Operationalize the Lessons-Learned Pipeline**
- *Objective:* `knowledge-curator.md` already exists per this project's
  agent roster, but `knowledge-vault/lessons/` contains only `.gitkeep` —
  find and fix why it isn't populating after real engagements have already
  run (including halberd-cost, which caught and disclosed its own $343M
  internal reconciliation error — exactly the kind of lesson this pipeline
  should have captured).
- *Why it matters:* audit reason #10 — zero institutional memory today.
- *Expected improvement:* likely a live-wiring bug fix, not new design —
  high impact for probably low effort.
- *Effort:* Medium (diagnose why the existing agent isn't writing back;
  verify `SKILL.md` phase 9/10 actually runs it).
- *Dependencies:* None.
- *Files:* `knowledge-curator.md`, `SKILL.md`, `knowledge-vault/lessons/`.
- *Priority:* **Critical** (high-impact, likely low-effort).

**I2 — Outcome Feedback Loop**
- *Objective:* A mechanism (manual at first — a follow-up field or form) to
  capture what actually happened after a client acted on a recommendation,
  feeding D4's calibration and I1's lessons pipeline with real ground
  truth.
- *Why it matters:* closes the loop between "what we recommended" and "what
  actually happened" — currently absent entirely.
- *Effort:* High — requires the Evidence Store to become durable
  cross-engagement (today it's explicitly in-memory, per-engagement,
  discarded after reconciliation, per the architecture audit). That
  persistence work is a hard prerequisite, outside this document's scope.
- *Dependencies:* Evidence Store persistence (architecture-track work).
- *Files:* new DB table, `apps/dashboard/backend/app/db.py`, `engagements.py`.
- *Priority:* Medium (high value, genuinely long-horizon — real outcomes
  take months to materialize).

**I3 — Cross-Engagement Pattern Detection**
- *Objective:* Once I1/I2 exist, periodically mine the lessons/outcomes
  corpus for recurring failure patterns (e.g., "reconciliation errors
  cluster around percentage-vs-revenue-base confusion" — already true once)
  and feed them back as a framework update or a new reviewer check.
- *Effort:* Medium (human-curated initially; doesn't need to be automated
  from day one).
- *Dependencies:* I1.
- *Files:* `knowledge-curator.md`, `reviewer.md` (receives new checks over
  time).
- *Priority:* Low (depends on I1/I2 maturing).

---

### J. Reporting

**J1 — Board Deck / Slide-Format Output**
- *Objective:* Generate a board-deck-appropriate slide outline (title +
  governing thought per slide — Minto's own "one message per page"
  standard) alongside the current markdown report, using the slide-
  generation tooling already available in this environment.
- *Why it matters:* real board deliverables are usually decks, not memos.
- *Effort:* Medium (report-writer's structured sections map reasonably well
  to a slide outline once B1 exists).
- *Dependencies:* B1, E1.
- *Files:* `report-writer.md` (new output mode), slide-tooling integration.
- *Priority:* Medium.

**J2 — Appendix-Grade Evidence Pack**
- *Objective:* A separate, fully-traceable appendix (every number, source,
  and assumption, cross-referenced) distinct from the concise board
  narrative, so the narrative can stay brief while due-diligence-grade
  backup exists on request.
- *Effort:* Low–Medium (largely a rendering/packaging task over data that
  already exists in the ledger/evidence infrastructure).
- *Dependencies:* Existing P1/P2 ledger/evidence infrastructure (ADR-010).
- *Files:* new render mode in `reporting/`, `report-writer.md`.
- *Priority:* Medium.

**J3 — Version-Controlled Report Redlines**
- *Objective:* When a report goes through rework cycles, preserve a visible
  diff/changelog of what changed and why.
- *Effort:* Low (the underlying markdown revisions already exist in
  `engagements/`; this is a diff-rendering convenience).
- *Dependencies:* None.
- *Files:* small standalone tooling script.
- *Priority:* Low.

---

### K. Framework Improvements

**K1 — Deepen Existing Framework "Common Risks/Mistakes" Sections**
- *Objective:* Expand from one bullet each (current state — Porter's, 7S,
  BCG matrix all confirmed template-identical, ~60 lines, one-liner risks)
  to a genuine limitations discussion, for the ~15 most-frequently-selected
  frameworks first.
- *Why it matters:* gives A5's `when_not_to_use` check real substance, and
  gives analysts genuine judgment cues instead of a superficial one-liner.
- *Effort:* Medium (content work).
- *Dependencies:* A5.
- *Files:* `knowledge-vault/frameworks/*.md` (top ~15).
- *Priority:* Medium.

**K2 — Framework Usage Analytics**
- *Objective:* Track which frameworks are actually selected across
  engagements; flag frameworks never selected (dead weight) or always
  selected regardless of case type (possible template-forcing signal).
- *Effort:* Low (logging + a periodic report).
- *Dependencies:* None.
- *Files:* `telemetry/`, a small analytics script.
- *Priority:* Low.

---

## 3. Sequencing

**Phase 0 — Foundational fixes** (mostly cheap, several are bug-fix-shaped):
E1, I1, D1, A5 (top frameworks only), C5, C6.

**Phase 1 — Core reasoning & judgment upgrade:**
A1, A2, B1, C1, C2, C3, D2, B2.

**Phase 2 — Governance hardening:**
F1, F2, F3, F4, G1, G3, G4, B3.

**Phase 3 — Communication & delivery quality:**
E2, E3, E4, E5, E6, J1, J2.

**Phase 4 — Knowledge depth & retrieval:**
H1, H2, H3, A4, K1, H4.

**Phase 5 — Advanced capability:**
G2, D3, D4, I2, I3, H5, H6.

**Phase 6 — Polish:**
C4, C7, J3, K2.

Dependencies flow mostly forward (Phase 1 items are prerequisites for much
of Phase 2/3), but Phase 0 and the start of Phase 1 can run in parallel —
none of E1/I1/D1/A5/C5/C6 block or are blocked by A1/A2/B1.

## 4. Three tiers of ambition

**4.1 — Minimum to reach "strong boutique consulting firm" level:**
Phase 0 in full, plus A1, A2, B1, C1, C2, C3, D1, D2 from Phase 1, plus a
*scoped* version of F1 (review only the frameworks/industries actually used
across current engagements, not all 63 files at once) and G1 (human
sign-off). This closes the root-cause gap, the hypothesis-driven gap, the
observation/implication separation, the cost-of-inaction gap, the
quantified-pressure-test gap, the reconciliation gap, gives the system a
real "no" verdict, and puts a human in the loop before delivery. A boutique
firm's actual quality bar is met by rigorous methodology plus partner
review — not by a fully-reviewed 63-framework library or persona-panel
board simulation.

**4.2 — Additional changes to reach MBB Partner-quality:**
The rest of Phase 2 in full (complete F1 knowledge review, F3 structural
model independence, F4 tiering, G3, G4), the rest of Phase 3 (full
communication polish — audience adaptation, hedge/redundancy detection,
board decks, evidence packs), H1 (semantic retrieval) and H3 (real
benchmarks) from Phase 4, D3 (ranker live-wiring), and G2 (board
simulation) from Phase 5. This is what separates "a good boutique
deliverable" from "indistinguishable from an MBB deliverable": structurally
independent governance (not correlated-model review), a fully reviewed
knowledge base, real semantic retrieval instead of keyword matching,
genuine benchmark data, and a persona-panel pressure test that simulates
the actual room the recommendation will be presented to.

**4.3 — Optional enhancements (quality improvements, not required):**
H5 (non-US localization), H6 (multi-stakeholder modeling — valuable but
scope-dependent on target client base), I2/I3 (outcome feedback loop and
pattern mining — genuinely valuable long-term but can't be forced quickly),
D4 (confidence calibration, depends on I2), K2 (framework usage analytics),
J3 (report redlines), C4 (trade-off table — most of its value is already
captured by C3), C7 (ramp-up checklist — a refinement of C3's territory),
A3 (value-of-information sequencing — a real efficiency gain, but not a
trust/quality gap the audit flagged directly), H4 (framework combination
guidance).

## 5. What this document does not decide

This is a design document. It does not authorize implementation of any
item. Per this project's standing rule, each phase (or, for Critical items,
each individual item) requires its own explicit go-ahead before work
starts — consistent with how P1–P3.5 of ADR-010 were each separately
approved rather than greenlit as a block.
