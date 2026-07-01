---
title: M1 (Engagement State) — Sub-Milestone Decomposition
status: Approved
date: 2026-06-30
parent_milestone: M1 (Implementation-Roadmap.md)
governing_adr: ADR-002 (Engagement State)
tags: [implementation, m1, decomposition]
---

# M1 — Engagement State: Sub-Milestone Decomposition

Decomposition of the M1 (Engagement State) milestone into small, independently
testable sub-milestones. Governed by ADR-002; conforms to the M0 Definition of Done.

## Principles
- **Static shape first, then dynamics.** Build models → facade → events → projection
  → invariants → concurrency → persistence → replay. The two correctness-critical
  pieces (projection, invariants) are isolated and heavily tested.
- **File-backed only.** The Ruflo AgentDB backend is deferred to M7, behind the same facade.
- **Facade is the sole public seam (from M1.3).** The public surface of the `state`
  package = the Facade + the domain models used as its arguments/returns. All
  mechanisms (projection, invariants, concurrency, persistence, replay) live in
  **private modules** (underscore-prefixed, not re-exported), guarded by an
  export-surface test (and `import-linter` once other packages consume `state`).
- **Performance is tested.** `pytest-benchmark` benchmarks for projection, validation,
  and replay at 10 / 100 / 1,000 / 10,000 events are part of the automated suite.
- **Traceability.** `docs/implementation/traceability-ADR-002.md` maps every ADR-002
  validation rule → test id(s), assembled at M1.6 (folding in the record-level rules
  first tested at M1.1).

## Sequence
M1.1 → M1.2 → **M1.3 (Facade)** → M1.4 → M1.5 → {M1.6, M1.7} → M1.8 → M1.9

| # | Sub-milestone | Complexity |
|---|---|---|
| M1.1 | Evidence & Assumption ledgers | Low–Med |
| M1.2 | Section models + full `EngagementState` aggregate | Medium |
| M1.3 | Engagement State Facade (public API + privacy boundary) | Low–Med |
| M1.4 | Event model (envelope + catalog) | Medium |
| M1.5 | Projection (deterministic fold) + benchmark | High |
| M1.6 | Invariants & validation + benchmark + traceability matrix | High |
| M1.7 | Concurrency, versioning & corrections | Med–High |
| M1.8 | Persistence — append / save / load | Medium |
| M1.9 | Replay — rebuild / projection-driven / snapshots / recovery + benchmark | Medium |

---

## M1.1 — Evidence & Assumption Ledgers
- **Objective:** model the two first-class ledgers, enforcing every record-level ADR-002 rule at the model boundary.
- **Scope:** `Evidence`, `Assumption`, enums; record-level rules only (evidence type→required fields via a modular rule registry; load-bearing→breakeven; confidence ∈ [0,1]). **Out:** aggregate/referential invariants, containers, events, projection, persistence.
- **Components:** `packages/state/ledgers.py`; `tests/state/test_ledgers.py`.
- **Dependencies:** M0.
- **Acceptance Criteria:** valid records per type construct; type-required omissions rejected; load-bearing-without-breakeven rejected; confidence bounds enforced; round-trip lossless.
- **Automated Tests:** parametrized positive/negative per evidence type; breakeven rule; confidence bounds; round-trip; enum values.
- **Exit Criteria:** all record-level rules enforced + tested; green gate.
- **Complexity:** Low–Medium. **Risks:** conditional-required logic → exhaustive matrix.

## M1.2 — Section Models & Full `EngagementState` Aggregate
- **Objective:** model all remaining ADR-002 sections; compose the complete state; regenerate JSON Schema.
- **Scope:** problem/objectives/constraints/stakeholders/classification/gaps/plan/framework/issue-tree/knowledge-refs/AnalysisBlock×5/reviewer/challenge/recommendations/confidence/deliverables/knowledge-links; compose `EngagementState`. **Out:** events, projection, invariants, concurrency, persistence.
- **Components:** `packages/state/sections/*` (private), updated aggregate, regenerated schema.
- **Dependencies:** M1.1.
- **Acceptance Criteria:** each section valid/invalid; full-state round-trip; section-coverage test vs ADR-002; schema drift test passes.
- **Automated Tests:** per-section; full-state round-trip; coverage test; schema-drift; enum coverage.
- **Exit Criteria:** complete typed shape; schema current; green gate.
- **Complexity:** Medium. **Risks:** omission → coverage test traced to ADR-002.

## M1.3 — Engagement State Facade (public API + privacy boundary)
- **Objective:** establish the sole public entry point and make mechanisms private.
- **Scope:** `EngagementState` facade exposing operations available now (create, current-state accessor, shape-validate, serialize); curate the `state` public surface; private modules for internals. Later sub-milestones implement their operations (append_event, rebuild, load/save) behind it. **Out:** event/projection/persistence logic (their own sub-milestones).
- **Components:** `packages/state/facade.py`, curated `packages/state/__init__.py` (`__all__`), export-surface test.
- **Dependencies:** M1.2.
- **Acceptance Criteria:** public API = facade + models only; internals not importable via the public surface; facade round-trips a state.
- **Automated Tests:** export-surface allowlist test; facade construct/get/validate/serialize.
- **Exit Criteria:** facade + privacy boundary in place; green gate.
- **Complexity:** Low–Medium. **Risks:** leakage → allowlist test (+ import-linter later).

## M1.4 — Event Model (envelope + catalog)
- **Objective:** immutable event envelope + full catalog.
- **Scope:** `Event` envelope, `EventType` (~40 per ADR-002), per-event payload models, frozen/immutable. **Out:** applying events (M1.5).
- **Components:** `packages/state/_events.py` (private).
- **Dependencies:** M1.2.
- **Acceptance Criteria:** each event constructs; immutable; unknown type rejected; every ADR-002 event present; round-trip.
- **Automated Tests:** per-type construction; immutability; catalog-completeness; round-trip.
- **Exit Criteria:** complete immutable catalog; green gate.
- **Complexity:** Medium. **Risks:** payload/section drift → reference section models + completeness test.

## M1.5 — Projection (deterministic fold) + benchmark
- **Objective:** materialize state by folding an ordered event log.
- **Scope:** pure `apply` / `project`; compensating events; empty log → initial; `state_version = last seq`. **+ projection benchmark** at 10/100/1k/10k. **Out:** invariant rejection, concurrency, persistence.
- **Components:** `packages/state/_projection.py` (private); `tests/state/test_projection.py`; `tests/perf/test_projection_bench.py`.
- **Dependencies:** M1.2, M1.4.
- **Acceptance Criteria:** golden logs → expected state; determinism; compensating events correct; benchmark thresholds met.
- **Automated Tests:** golden fixtures; determinism; per-compensating-event; empty-log; `pytest-benchmark` at 4 scales.
- **Exit Criteria:** deterministic projection + recorded benchmark baselines; green gate.
- **Complexity:** High. **Risks:** fold/compensation bugs → golden fixtures + determinism tests.

## M1.6 — Invariants & Validation + benchmark + traceability matrix
- **Objective:** enforce ADR-002 §Validation-Rules on state + transitions.
- **Scope:** phase preconditions; forbidden transitions; referential integrity; cross-field invariants (confidence ≤ min evidence; ≥1 validated evidence; state_version == max seq). **+ validation benchmark** at 4 scales. **+ traceability matrix.** **Out:** concurrency (M1.7).
- **Components:** `packages/state/_invariants.py` (private); `tests/state/test_invariants.py`; `tests/perf/test_validation_bench.py`; `docs/implementation/traceability-ADR-002.md`.
- **Dependencies:** M1.2, M1.5.
- **Acceptance Criteria:** each rule enforced; valid passes; each violation detected + typed; transitions rejected; every rule mapped to ≥1 test.
- **Automated Tests:** one positive + one negative per invariant; transition matrix; referential integrity; validation benchmark.
- **Exit Criteria:** every rule enforced + tested + traced; green gate.
- **Complexity:** High. **Risks:** missing invariant → ADR-002 rules enumerated 1:1 into the traceability matrix.

## M1.7 — Concurrency, Versioning & Corrections
- **Objective:** safe concurrent evolution + versioning.
- **Scope:** monotonic seq; state_version; optimistic concurrency (stale-version reject); owner-exclusive section writes (R/W matrix); corrections only via events. **Out:** distributed/multi-process.
- **Components:** `packages/state/_concurrency.py` (private) + R/W-matrix data; `tests/state/test_concurrency.py`.
- **Dependencies:** M1.4, M1.5.
- **Acceptance Criteria:** disjoint appends interleave; stale-version rejected; non-owner write rejected; no mutate/delete path.
- **Automated Tests:** interleaved appends; stale-version; owner-violation; log-immutability; R/W conformance.
- **Exit Criteria:** enforced + tested; green gate.
- **Complexity:** Med–High. **Risks:** ordering/races → deterministic seq + conflict tests.

## M1.8 — Persistence (append / save / load)
- **Objective:** durable file-backed event log + snapshot.
- **Scope:** `engagements/<slug>/events.log` (append-only) + `state.json` (snapshot); atomic append/save; load. **Out:** rebuild/recovery (M1.9).
- **Components:** `packages/state/_store.py` (private); `tests/state/test_store.py`.
- **Dependencies:** M1.4 (events), M1.3 (facade surface).
- **Acceptance Criteria:** append→save→load round-trips; atomic writes (temp+rename); load returns persisted events/snapshot.
- **Automated Tests:** round-trip; atomicity; concurrent-append safety.
- **Exit Criteria:** durable persistence via the facade; green gate.
- **Complexity:** Medium. **Risks:** partial-write/atomicity → temp+rename + tests.

## M1.9 — Replay (rebuild / projection-driven / snapshots / recovery) + benchmark
- **Objective:** reconstruct state from the persisted log; snapshot + recover.
- **Scope:** rebuild-from-log (projection over persisted events); snapshot write/read; crash/recovery (rebuild when snapshot missing/stale; recover from truncated log to last valid event). **+ replay benchmark** at 4 scales. **← completes M1.**
- **Components:** `packages/state/_replay.py` (private); `tests/state/test_replay.py`; `tests/perf/test_replay_bench.py`.
- **Dependencies:** M1.5, M1.8.
- **Acceptance Criteria:** rebuild-from-log == snapshot; resume after simulated crash; benchmark thresholds met.
- **Automated Tests:** replay-equals-snapshot; crash/resume (truncation); determinism across reload; replay benchmark.
- **Exit Criteria:** durable, resumable, benchmarked state; green gate. **M1 complete.**
- **Complexity:** Medium. **Risks:** recovery edge cases → truncation/corruption tests.
