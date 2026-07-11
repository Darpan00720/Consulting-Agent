---
adr: 006
title: Mandatory Governance Gates & Live Report Validation
status: Accepted
date: 2026-07-09
deciders: [Principal Architect]
relates: [ADR-002 §Quality Gates, ADR-005 Governance agents, RC1 Validation Campaign]
supersedes: [solve-case SKILL "lightweight may skip reviewer" rule]
tags: [governance, gates, validation, orchestration, convergence]
---

# ADR-006 — Mandatory Governance Gates & Live Report Validation

> **Status:** Accepted (RC1.2 Architecture Convergence Sprint).
> **Scope:** Resolves two inconsistencies the RC1 validation campaign found
> between the intended architecture (ADR-002) and the live orchestration
> (`solve-case` SKILL): (WI-3) the lightweight pipeline skipping the Reviewer,
> and (WI-2) the deterministic validation layer not running on the live path.

---

## 1. Context

The RC1 Validation Campaign (`docs/reviews/v1.0-Validation-Campaign.md`) found:

- **F-3** — the `solve-case` SKILL sanctioned a "lightweight" pipeline that
  skips the Reviewer gate. In pilot case C09 this let a cross-analyst numeric
  inconsistency (a $343M cost-base disagreement) reach the Challenger uncaught;
  the Challenger caught it, but consistency enforcement should not depend on a
  single gate.
- **F-4** — the deterministic `reporting` validation layer
  (`check_render_ready`, `enforce_render_ready`, `validate_consistency`) was
  never invoked on the live path. The live pipeline passes markdown between
  agents and never builds the `EngagementState` those functions validate, so
  the structural anti-hallucination guards did not fire at runtime.

## 2. Evidence

- **ADR-002 §Quality Gates** defines `quality_gates` as a list that *"Proves
  mandatory gates ran; blocks skipping."* The lifecycle places `review` as a
  required state between `evidence_validation` and `challenge`. `Evidence.validated`
  is *"Set true only by Reviewer."* The intended architecture therefore already
  makes the Reviewer a **mandatory** gate; the SKILL's skip rule was drift.
- **ADR-005** lists Reviewer (analysis gate) and Challenger (recommendation
  gate) as the two gatekeepers, run on every engagement.

The architecture did not need to change to answer WI-3; the *implementation*
did. This ADR ratifies the existing intent and removes the drift.

## 3. Decision

### 3.1 Governance gates are mandatory in every pipeline mode

The **Reviewer** and **Challenger** run on **every** engagement. "Lightweight"
means dispatching *fewer analysts* for a simpler case — never skipping a gate.
The `solve-case` SKILL operating rule that permitted skipping the Reviewer is
removed.

Rationale: the Reviewer's five checks (MECE, evidence-traceability, consistency,
calibration, gap-closure) are inexpensive relative to the analyst dispatches and
are the designed place to catch cross-analyst inconsistency *before* it reaches
the Challenger. Cross-analyst numeric consistency (RC-3) is the check that the
lightweight path was silently dropping.

### 3.2 A deterministic live validation gate blocks report delivery

Before a report is produced, the orchestrator serializes the engagement to
`engagements/<slug>/state.json` (conforming to `EngagementState`) and runs the
blocking gate:

```
uv run python scripts/validate_engagement.py <slug>
```

implemented by `packages/orchestration/report_gate.py`, which runs
`reporting.check_render_ready` **and** `reporting.validate_consistency` and
combines their findings. Behaviour:

- **Pass** → report generation may proceed (SKILL Phase 8b).
- **Fail** → report generation is **blocked**; the gate emits actionable
  diagnostics (`(check:rule) [section] detail`) naming the responsible section.
  The orchestrator routes each issue to the owning agent, fixes `state.json` at
  source, and re-runs. **No report may bypass the gate**, and the gate — not the
  report-writer's own judgement — is the authority that both governance verdicts
  cleared.

This is the "state bridge + gate script" option: the LLM `report-writer` still
authors the narrative report, but a deterministic structural gate stands between
the analysis and the deliverable.

## 4. Consequences

- The lightweight pipeline is now: classifier → framework-selector → 1–2
  specialists → **reviewer** → **challenger** → report-writer, plus the Phase-8a
  gate. It is cheaper than the full pipeline only in analyst count.
- The `challenger` precondition (`reviewer_notes.verdict == approved`) is now
  always satisfiable by construction; the RC1 "waived by lightweight path"
  handling is obsolete.
- `packages/state/**`, `persistence/**`, `replay/**`, and `reporting/**` are
  unchanged. The gate only *constructs* and *reads* existing `EngagementState`
  models; it adds no new state.
- New code lives in `packages/orchestration/` and `scripts/validate_engagement.py`.

## 5. Alternatives considered

- **Replace the LLM report-writer with `render_report(state)`** (fully
  deterministic report). Rejected: it discards the narrative quality of the
  LLM-authored report; the goal is a validation *gate*, not report generation.
- **A new "lightweight consistency gate"** substituting for the full Reviewer.
  Rejected: ADR-002 already makes the Reviewer mandatory, so the simpler,
  convergent answer is to always run it.
