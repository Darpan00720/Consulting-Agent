---
title: Architecture Checkpoint — M1 Implementation Review
status: Review (pre-M1.7 gate)
date: 2026-07-02
reviewed-range: e4dcb9a (architecture v1.0) … 962f732 (M1.6 CHANGELOG), 41 commits, clean tree
scope: M0 — M1.6
verdict: GO (with conditions — see §14)
---

# Architecture Checkpoint — M1 Implementation Review

A Principal Architect review of everything implemented from M0 through M1.6,
evaluated against the frozen v1.0 architecture (ADR-001…ADR-005) exactly as
approved. Every observation is classified **[Verified]** (directly evidenced in the
repository or by executing the quality gate at commit `962f732`), **[Inference]**
(a conclusion reasonably drawn from verified facts), or **[Unknown]** (cannot be
determined from the repository). No code was written or modified for this review.

Ground truth used throughout: at `962f732`, `make check` passes — ruff clean, black
clean, mypy `--strict` clean over 41 source files, **110 tests passed** — and
`pytest --cov=state` reports **99% total coverage (1,320 statements, 3 missed:
`projection.py:136,437`, `schema.py:23`)** with **100% on every
`state/validation/*` module**. **[Verified — executed during this review session]**

---

# 1. Executive Summary

**Overall quality: high, with a small number of honest gaps.** The implemented core
(engagement state model, event catalog, projection, validation) matches the
approved architecture closely — in one dimension (event taxonomy) *exactly*: all 49
event types in ADR-002's Event Model table are implemented, with zero missing and
zero extra **[Verified — programmatic diff of `EventType` against the ADR table]**.
Engineering discipline is real, not claimed: strict typing, generated (never
hand-edited) JSON Schema with a drift test, a frozen facade, per-rule traceability,
and a green gate at every milestone commit **[Verified — git history shows
41 single-responsibility commits, each milestone ending in test+docs commits]**.

**Readiness:**

- **M1.7 Concurrency — ready, with two items to resolve in its plan.** The
  foundations M1.7 needs already exist: `EngagementMetadata.state_version`
  ([models.py:59](../../packages/state/models.py)), `EventMetadata.seq`
  ([events.py:148](../../packages/state/events.py)), `actor`/`source` on every
  event, and an immutable event union. **[Verified]** Two open issues belong in the
  M1.7 plan before code: (a) projection contains **no reference to `seq`** — it
  folds events in caller-supplied order **[Verified — zero grep hits for `seq` in
  projection.py]**, so seq assignment/ordering discipline is entirely M1.7's to
  define; (b) `Engagement.get_state()` returns the **live** state object, and
  `EngagementState` is not frozen, so callers can mutate list sections in place
  ([facade.py:81-83](../../packages/state/facade.py),
  [core/base.py:20-23](../../packages/core/base.py)) — acceptable pre-concurrency,
  but M1.7's optimistic-locking semantics are unsound if reads alias the write
  target. See §13.
- **M1.8 Persistence — ready.** There is **no IO anywhere in `packages/state`**
  (the only `json` import is schema generation; the only `time` import is the
  validation stopwatch) **[Verified — import scan]**, so persistence lands behind a
  clean seam. The decomposition already reserves
  `engagements/<slug>/events.log` + `state.json`
  ([M1-Decomposition.md:118-120](../implementation/M1-Decomposition.md)).
- **M1.9 Replay — ready.** Replay-as-composition is already a tested property of
  projection ([test_projection.py](../../tests/state/test_projection.py)), and the
  `projection_version` policy for rebuild/migration is documented
  ([projection-versioning.md](../architecture/projection-versioning.md)).
  **[Verified]**

The one material completeness gap is in validation rule coverage: four ADR-002
gate-entry precondition rules are not yet implemented (§8, TD-002). This is
additive work (new rules in existing registries; no interface change) and does not
block M1.7 — but it must be scheduled, because M1-Decomposition listed "phase
preconditions" in M1.6's scope. **[Verified — see §8]**

---

# 2. ADR Compliance Matrix

| ADR | Status | Evidence | Notes |
|---|---|---|---|
| **ADR-001** System Architecture | **Partially Implemented** | Repo structure per §9 exists for: `.claude-plugin/marketplace.json`, `plugins/ruflo-stratagent/` (plugin.json, commands, skills, 7 agents, 9 framework sheets, README), `engagements/`, `docs/architecture`, `.claude` symlinks **[Verified — `ls` of repo root and plugin]**. `knowledge-vault/`, `eval/`, `apps/` do not exist **[Verified]**. Layers 1–7 as running software: only the Engagement State slice of the domain layer exists as code. | Expected: layers are delivered by M2–M10 per the approved roadmap **[Verified — Implementation-Roadmap.md]**. `packages/`, `schema/`, `scripts/`, `tests/`, `Makefile` are **not** in ADR-001 §9's tree — they were introduced by the approved M0 plan (recorded in CHANGELOG M0), a sanctioned addition, not silent drift **[Verified — CHANGELOG; ADR-001 §9 text]**. ADR-001 §9 was never amended to show them **[Verified]** — flagged in §11. |
| **ADR-002** Engagement State | **Partially Implemented** (on plan) | All §1–§25 sections modeled (`models.py`, `sections/*`, `ledgers.py`); §2 lifecycle-audit fields present (`phase_history`, `quality_gates`, `pending_requirements`) **[Verified]**. §26/Event Model: 49/49 events, exact name parity, every event in exactly one category **[Verified — programmatic diff]**. Projection (M1.5) and validation (M1.6) implemented. | Remaining ADR-002 scope — concurrency rules, `state_version == max(seq)`, persistence, replay — is explicitly owned by M1.7–M1.9 **[Verified — M1-Decomposition §M1.7–M1.9; user approval directive recorded in CHANGELOG M1.6 notes]**. Validation rule coverage is partial — full disposition in §8. One approved deviation: ADR's `blocked_on` broadened to `pending_requirements` (documented, CHANGELOG M1.5) **[Verified]**. |
| **ADR-003** Knowledge Architecture | **Not Started** | No `knowledge-vault/` directory; `packages/knowledge/__init__.py` is a 1-line scaffold **[Verified]**. Graphify CLI installed as a tool but nothing indexed **[Verified — no vault to index; no graph artifacts in repo]**. | Scheduled M2–M3 per roadmap. Not a compliance failure. |
| **ADR-004** Consulting Knowledge Library | **Not Started** | The ADR-004 library (15 domains + catalogs) does not exist. The 9 files in `plugins/ruflo-stratagent/knowledge/frameworks/` are the pre-ADR prototype cheat sheets **[Verified — file listing]**. | The prototype predates the packages-based build and does not implement ADR-004's structure **[Inference — from content scope: 9 sheets vs 15 domains + catalogs]**. Scheduled M2+. |
| **ADR-005** Agent Specifications | **Not Started** | No agent implementations in `packages/` (planning/analysis/governance/reporting are 1-line scaffolds) **[Verified]**. The plugin ships 7 prototype agent prompt files; ADR-005 specifies 16 agent contracts **[Verified — 7 files in `plugins/ruflo-stratagent/agents/`]**. | The 7 prototype agents are the pre-architecture demo, not ADR-005 implementations. Scheduled M4–M6. |

No ADR is **Diverged**: every deviation found is either user-approved and
documented (pending_requirements, `packages/` layout, identifier harmonization) or
scheduled future scope. **[Verified — each deviation has a CHANGELOG/decomposition
record]**

---

# 3. Package Architecture Review

**Layout** **[Verified — file listing, 3,453 LOC across 38 Python files]**:

```
packages/
  core/        base model, settings, logging          (81 LOC)
  common/      errors, value objects, DomainObject    (61 LOC)
  state/       THE M1 DELIVERABLE                     (~3,300 LOC)
    sections/  §3–§25 section models (7 modules)
    validation/ 5 rule groups + types + runner (M1.6)
    enums, identifiers, ledgers, models, events,
    projection, facade, schema
  knowledge/ planning/ analysis/ governance/ reporting/   (1-line scaffolds)
```

- **Separation of concerns — good.** Each `state` module has one responsibility:
  models describe, events record, projection folds, validation judges, facade
  exposes, schema generates. Projection and validation share nothing but the models
  **[Verified — imports]**.
- **Dependency direction — correct and strictly one-way.** `core` imports only
  stdlib/pydantic; `common` imports only `core`; `state` imports `common` + `core`;
  nothing imports `state` except scripts/tests **[Verified — full import scan,
  §4]**.
- **Boundaries — enforced, not aspirational.** The public surface is a curated
  `state.__all__` (75 names) guarded by an allowlist test; `state.validation` is
  deliberately **not** exported **[Verified — `state.__all__` inspection;
  tests/state/test_facade.py allowlist]**.
- **Cohesion — high** within modules (e.g., all five rule groups have identical
  shape: pure validators + a `RULES` registry). **[Verified]**
- **Coupling — low**, with one deliberate exception: `validation/_util.py` and
  `projection.py` both hard-code the five analysis-section attribute names
  (`_ANALYSIS_ATTRS` / `_ANALYSIS_FIELDS`) **[Verified — both files]**. Two copies
  of the same field-name knowledge is a mild smell; a third copy would justify
  centralizing it **[Inference]**.
- **Extensibility — good.** New event = new frozen model + reducer + union member
  (with a reducer-completeness test that fails if the reducer is missing); new rule
  = new `ValidationRule` in a registry (with a 1:1-test guard). **[Verified — test
  suite structure]**
- **Maintainability — good.** mypy `--strict` across everything; no `Any`
  leakage in public signatures; docstrings state each module's contract.
  **[Verified — mypy config + clean run]**

**Architecture smells found** (all minor):
1. Duplicated analysis-field maps (above). **[Verified]**
2. `Finding` (validation) is a stdlib dataclass while `Violation`/`ValidationReport`
   are Pydantic models — two modeling idioms inside one subpackage
   **[Verified — validation/types.py]**. Defensible (Finding is internal plumbing,
   never serialized) **[Inference]**, but worth a comment or consistency pass.
3. Empty scaffold packages ship in the source tree years before use — harmless, but
   they will silently accept accidental imports **[Inference]**.

---

# 4. Dependency Analysis

Full import scan of `packages/` **[Verified]**:

```
core      →  (stdlib, pydantic, pydantic-settings only)
common    →  core
state     →  common, core
  state.sections    →  common, core, state.enums/identifiers
  state.validation  →  state.models/sections/ledgers/enums, common, core
  state.projection  →  state.models/sections/ledgers/events/identifiers
scripts   →  state          tests  →  state, common, core
```

- **Circular dependencies: none.** `core` has no internal imports (only
  intra-package `core.logging → core.config`); `common` imports only `core`
  **[Verified — grep of every import line in both packages]**.
- **Hidden coupling:** the analysis-field name duplication (§3). Also,
  `validation` and `projection` both bind to section model field names — any §3–§25
  rename touches three places **[Verified]**. Acceptable at current scale
  **[Inference]**.
- **Inappropriate imports: none found.** The earlier M1.6 near-miss — a
  `StateValidationError(ValidationReport)` in `common` would have created a
  `common → state` cycle — was resolved by moving the error into
  `state.validation` **[Verified — common/errors.py now contains only
  `StratAgentError`; runner.py defines the specific error]**.
- **Layering violations: none.** Direction matches ADR-001's "dependencies flow
  downward only" **[Verified]**.
- **IO discipline:** zero filesystem/network imports in `packages/state` (only
  `json` in schema.py for schema *rendering*, `time` in runner.py for the report
  stopwatch) **[Verified — import scan]**. This is the strongest single signal of
  M1.8 readiness.

---

# 5. Engagement State Review

- **State model:** `EngagementState` composes all ADR-002 §1–§25 sections plus the
  §2 lifecycle-audit fields; a state is valid with metadata alone (approved
  optionality model) **[Verified — models.py:63-113;
  tests/state/test_engagement_state.py]**.
- **Immutability — layered, not uniform. [Verified]**
  - Events: **fully frozen** (`ConfigDict(frozen=True)` on `EventMetadata` and
    `_EventBase`) — events.py:145, 158.
  - Identity: `DomainObject.id` and typed-id overrides are field-frozen —
    common/models.py:22.
  - Aggregate: `EngagementState` is **not frozen** — `StratAgentModel` sets
    `extra="forbid"` + `validate_assignment` only (core/base.py:20-23). List
    sections are ordinary mutable lists.
  - Facade: exposes no mutation methods, but `get_state()` returns the **live**
    object, not a copy (facade.py:81-83), so `state.evidence.append(...)` by a
    caller mutates the engagement in place. **[Verified]** Under M1.3's approved
    intent ("do not expose live EngagementState…use get_state()/snapshot()") this
    is a gap in spirit if not in letter **[Inference]** — carried to §13/§12, to be
    settled in the M1.7 plan (copy-on-read, deep-freeze, or documented convention).
- **Event-sourcing assumptions:** log-is-truth is honored — projection never
  invents identity or time (ids from `event_id`, timestamps from `occurred_at`,
  `_EPOCH` seed) **[Verified — projection.py; determinism tests]**.
- **Lifecycle fields:** `phase_history`/`quality_gates`/`pending_requirements`
  populated only by projection reducers **[Verified — no other writer in
  packages/]**.
- **Projection / validation:** see §7 / §8.
- **Versioning readiness: [Verified]** three version fields exist with distinct,
  documented meanings — `EngagementMetadata.state_version` (=0 everywhere today;
  M1.7 will bind it to max seq), `EngagementMetadata.schema_version` (model shape),
  `EngagementState.projection_version` (fold algorithm; policy doc exists).
  **Nothing maintains `state_version` yet** — it is a declared field awaiting
  M1.7, not a wired invariant **[Verified — no assignment outside default]**.

**Missing concepts before M1.7** (to appear in its plan, not necessarily as code
now): seq-assignment authority and ordering contract (§7); read-aliasing decision
for `get_state()` (above); the ADR's owner-exclusive section-write matrix
(ADR-002 §Concurrency) has **no machine-readable representation yet** — agents'
section ownership exists only as ADR prose **[Verified — no such structure in
packages/]**.

---

# 6. Event Architecture Review

- **Taxonomy:** 49 event models in a discriminated union keyed on `type`;
  **exact parity with ADR-002's Event Model table — 0 missing, 0 extra**
  **[Verified — programmatic name diff run during this review]**.
- **Metadata:** `EventMetadata` carries `event_id`, `engagement_id`, `seq`,
  `occurred_at`/`recorded_at` (business vs system time), `actor` vs `source`,
  `schema_version`, `causation_id`, `correlation_id` — all six approved M1.4
  adjustments present **[Verified — events.py:141-155]**.
- **Immutability:** enforced by config, not convention (`frozen=True` on the
  envelope and every event base) **[Verified]**.
- **Identifier model:** `NewType` ids (EventId, EngagementId, EvidenceId, …) used
  in both events and domain models — one identifier system, str-serialized
  (schema-invariant) **[Verified — identifiers.py; schema drift test green]**.
- **Categories:** `EVENT_CATEGORIES` maps every `EventType` to exactly one
  category; completeness is machine-checked **[Verified — executed
  `set(EVENT_CATEGORIES) == set(EventType)` → True; plus the existing test]**.
- **Payload consistency:** events are self-contained (payloads carry data + refs by
  immutable id, per the documented Event-Design-Principles) **[Verified — doc
  exists; spot-checked event models]**. Whether all 49 payloads satisfy
  self-containment in every field: **[Unknown — not exhaustively re-audited in this
  review; it was the M1.4 review criterion]**.
- **Schema evolution readiness — partial.** Per-event `schema_version` exists, but
  there is **no upcasting/migration mechanism** — old-version events have no
  defined path into new models **[Verified — no such code exists]**. Acceptable
  pre-persistence **[Inference]**; must be addressed no later than M1.8/M1.9 when
  logs become durable.

**Weaknesses:** (1) `seq: int = 0` default means unsequenced events are
representable and indistinguishable from "first" **[Verified — events.py:148]** —
M1.7 must decide whether unassigned seq is an error. (2) No upcasting (above).

---

# 7. Projection Review

- **Determinism: verified by test, and structurally.** All reducer-created objects
  derive ids from `event.metadata.event_id` and times from `occurred_at`; the seed
  state uses `_EPOCH` and placeholder metadata; `project(log) == project(log)` and
  replay-equals-composition are asserted in tests **[Verified —
  projection.py:111-122; test_projection.py]**.
- **Purity:** no IO, no clock, no randomness in the module **[Verified — import
  scan; the only datetime use is the `_EPOCH` constant]**.
- **Reducer design:** `functools.singledispatch`, one reducer per event, default
  no-op; a reducer-completeness test fails if any of the 49 events lacks a
  registered reducer **[Verified — test suite]**.
- **Replay readiness — one contract gap:** projection **ignores `seq` entirely**
  and folds in iteration order **[Verified — zero `seq` references in
  projection.py]**. Correct replay therefore currently depends on the caller
  supplying events in order. That is a fine division of labor *if* M1.7/M1.9 make
  the store the ordering authority — but the contract ("caller must supply
  seq-ordered events") is **not written down anywhere** **[Verified — not in
  projection.py docstrings nor docs/api]**. Must be stated in the M1.7 design.
- **Scalability:** benchmarks (single cold run, Apple M3, documented methodology)
  — 10 ev ≈ 84–98µs, 100 ≈ 155–209µs, 1k ≈ 1.5ms, 10k ≈ 32–33ms across the three
  runs recorded this week **[Verified — projection-baseline.md + two gate runs in
  this session]**. Near-linear with a mild superlinear tail from immutable list
  rebuilds; engagement-scale logs (10²–10³ events) are sub-2ms. No optimization
  performed or currently justified **[Verified — baseline doc states the policy]**.
- Empty-log projection yields placeholder metadata (`EngagementId("")`,
  `_EPOCH`) by approved design (M1.5 adjustment #3) **[Verified]** — persistence
  (M1.8) should never save such a state; worth an explicit guard when saving
  **[Inference]**.

---

# 8. Validation Review

**Architecture: [Verified]** five rule registries (structural, lifecycle,
referential, business, governance), each rule a first-class `ValidationRule` (id,
group, severity, ADR reference, description, validator); validators are pure
`state → list[Finding]` and import nothing from each other; the runner is the sole
orchestrator and produces a `ValidationReport` (validity, per-severity counts,
duration, groups, violations). Rule-id namespace frozen and guarded by tests.
Validation shares zero code with projection. 17 rules: 14 ERROR, 3 WARNING;
INFO/FATAL are defined but currently unused **[Verified — registry inspection]**.

**Traceability:** `traceability-ADR-002.md` + `traceability.json` are generated
from the registry; 17/17 rules have matching slug-named tests; freshness and 1:1
mapping are test-enforced **[Verified — traceability.json parse: 17 rules, all
with tests]**.

**ADR-002 §Validation Rules — full disposition** (the honest accounting; ADR text
at ADR-002-Engagement-State.md:489-524):

| ADR-002 rule | Disposition | Evidence |
|---|---|---|
| **Gate preconditions** | | |
| Enter Planning (archetype + real_question; load-bearing gaps resolved) | **NOT IMPLEMENTED** | No rule checks planning-entry preconditions **[Verified — registry]** |
| Enter Specialist Analysis (non-empty tree, leaves owned, plan exists) | **PARTIAL** | STRUCT-001 checks leaf owners always; tree/plan presence at entry unchecked **[Verified]** |
| Enter Reviewer (leaves answered; findings evidenced) | **PARTIAL** | STRUCT-002 checks finding→evidence always; leaf-status precondition unchecked **[Verified]** |
| Enter Challenger (review approved) | **NOT IMPLEMENTED** (ordering only via LIFE-003) **[Verified]** |
| Generate Report (both gates) | **COVERED** — LIFE-001 **[Verified]** |
| Complete (report + accepted recommendation) | **COVERED** — LIFE-002 **[Verified]** |
| **Forbidden transitions** | | |
| Reporting without both gates | **COVERED** — LIFE-001 **[Verified]** |
| Skipping review/challenge | **COVERED** — LIFE-003 transition map **[Verified — lifecycle.py `_build_allowed`]** |
| Mutation after completed | **DEFERRED (M1.7 write layer)** — not statically checkable on a snapshot **[Inference]**; no write API exists yet **[Verified]** |
| Editing/deleting events | **DEFERRED (M1.8 store)**; events frozen at model level today **[Verified]** |
| Specialist writing another's section | **DEFERRED** — requires write-time actor context (M1.7+) **[Verified — deferral recorded in M1.6 DoD/CHANGELOG]** |
| **State invariants** | | |
| Evidence type→provenance | **COVERED (record level, M1.1)** — ledgers.py `_EVIDENCE_RULES` + model validator **[Verified]** |
| Load-bearing assumption → breakeven | **COVERED (record level, M1.1)** — ledgers.py:116-119 `_enforce_breakeven` **[Verified]** |
| Leaf has exactly one owner | **COVERED** — STRUCT-001 **[Verified]** |
| recommendation.confidence ≤ min(validated evidence) | **COVERED** — BIZ-001 via `confidence.overall`; faithful reading, since §22 has no confidence field and §23 defines `overall` as "min/weighted of supporting evidence" **[Verified — ADR §22/§23 text; Inference on equivalence]** |
| No recommendation without validated evidence | **COVERED** — BIZ-002 **[Verified]** |
| All refs resolve | **COVERED** — REF-001…REF-004 **[Verified]** |
| state_version == max(seq) | **DEFERRED (M1.7)** — field exists, invariant explicitly assigned to M1.7 by approval; *note:* M1-Decomposition line 100 still lists it under M1.6 scope — doc inconsistency (§11) **[Verified]** |
| **Concurrency rules (4)** | **DEFERRED (M1.7)** — explicit user directive: "M1.7 continues to own concurrency, versioning, persistence, and replay" **[Verified — recorded in CHANGELOG M1.6 notes]** |
| **Approval rules** | | |
| Gates approved only by the right role | **PARTIAL** — GOV-001 requires gate PASS records; `QualityGate.by` exists (lifecycle.py:32) but no rule checks *who* **[Verified]** |
| No self-approval | **DEFERRED** — needs actor conventions **[Verified — recorded deferral]** |
| Rejection carries actionable fix | **COVERED** — GOV-002 (+GOV-003 warning) **[Verified]** |

**Net:** 11 covered, 3 partial, 2 not implemented, and the rest deferred to their
explicitly-assigned milestones. So the answer to "is every ADR-002 validation rule
covered?" is **no — and the M1.6 DoD's claim that every §Validation-Rules item had
a rule was overstated for the gate-precondition family** **[Verified — this
review's own accounting]**. The gap is additive (new LIFE-005+ rules, frozen ids
preserved) and is logged as TD-002. A second gap: the generated traceability
matrix rows only cover *implemented* rules; deferred/record-level ADR rules have no
disposition record in it (TD-004) **[Verified — traceability.json contains exactly
the 17 registry rules]**.

**Extensibility:** adding a rule is one registry entry + one slug-named test; the
guards make omission loud. **[Verified — test_traceability.py]** One purity note:
`validate()` reads `time.perf_counter` for `duration_ms`, so reports are not
byte-identical across runs; the violation list itself is deterministic
**[Verified — runner.py]**.

---

# 9. Public API Review

- **Stability:** the facade is frozen at six methods (`create`, `from_state`,
  `from_json`, `get_state`, `validate`, `to_json`) with `EngagementProtocol` as the
  swappable contract; documented as Stable in docs/api/EngagementState.md
  **[Verified — facade.py; API doc]**.
- **Simplicity:** no mutation methods; state evolves only via the (future) event
  API — the facade cannot be misused to bypass the log **[Verified — no such
  methods exist]**.
- **Encapsulation — one caveat:** `get_state()` returns the live instance (§5).
  Also `Engagement.validate()` currently performs **Pydantic re-validation only**
  (`model_validate(model_dump())`, facade.py:85-87); it does **not** run
  `state.validation` — invariant checking is internal by approved M1.6 scope and
  will be surfaced later **[Verified]**. The API doc should not imply otherwise
  **[Unknown whether any consumer currently assumes invariant semantics — no
  external consumers exist yet]**.
- **Public surface:** `state.__all__` = 75 names (facade, protocol, aggregate +
  section models, enums, value objects, typed ids, event catalog), allowlist-tested;
  `state.validation` and `state.projection` are unexported **[Verified]**.
  75 names is large but justified: 49 of them are the event catalog, which the ADR
  makes deliberately public **[Verified — count; ADR-002 event contract]**. No
  *unnecessary* exports found — everything else is a model or enum a consumer
  composing states/events genuinely needs **[Inference]**.

---

# 10. Testing Review

- **Inventory:** 18 test files, 1,490 LOC, **110 tests, all passing** at `962f732`
  **[Verified — executed]**. Structure mirrors the package: per-module unit tests,
  projection determinism/purity/replay property tests, reducer-completeness, full
  49-reducer exercise, per-rule validation tests (negative per rule + branch
  tests), runner semantics, traceability guards, schema drift, facade allowlist.
- **Benchmarks:** projection (event-scaled) and validation (state-object-scaled,
  per the approved adjustment) at 4 sizes each, in-suite **[Verified]**.
  Methodology is a **single cold run** (`pedantic(rounds=1)`) — deliberately cheap,
  documented as indicative-only; the 10-object validation case showing ~800µs
  (larger than the 100-object case, ~71µs) is warmup noise and demonstrates the
  limitation **[Verified — bench output this session; caveat documented in
  projection-baseline.md]**.
- **Coverage:** state 99% overall; validation 100%; the 3 uncovered lines are two
  defensive branches in projection reducers (136, 437) and the schema `render()`
  line used only by the generation script **[Verified — coverage run]**.
- **Blind spots [Verified unless noted]:**
  1. **No property-based/fuzz testing** of projection (e.g., random event
     permutations, duplicate events) — order-sensitivity is untested because the
     ordering contract is undefined (§7).
  2. **No adversarial serialization tests** (malformed JSON into `from_json`,
     unknown enum values, forward-version events) — relevant from M1.8 on.
  3. Benchmarks assert only `report.valid`/state shape, not timing regressions —
     baselines are informational, nothing fails on slowdown (by design;
     acceptable) **[Inference on acceptability]**.
  4. `core/` and `common/` are tested only incidentally through `state`
     (coverage is measured with `--cov=state` only) **[Verified — Makefile `cov`
     target]**.

---

# 11. Documentation Review

- **ADRs:** five, frozen v1.0, internally consistent; Event-Design-Principles and
  projection-versioning extend them without contradiction **[Verified — read]**.
- **API docs:** EngagementState.md (Stable) and Events.md exist and match the
  implementation on the items spot-checked (lifecycle-audit fields,
  `projection_version`, `state_version` at line 108) **[Verified]**. Full
  field-by-field parity: **[Unknown — not exhaustively diffed in this review]**.
- **Implementation docs:** Roadmap, M1-Decomposition, BACKLOG (TD-001), M1.1
  retrospective, DEV guide, generated traceability pair **[Verified — all
  present]**.
- **Benchmark docs:** projection-baseline.md records environment, methodology,
  counts, timings + the honest single-run caveat **[Verified]**. **Gap:** no
  equivalent baseline document for the *validation* benchmarks — numbers exist
  only in test output **[Verified — docs/performance contains only the projection
  baseline]**.
- **Changelog:** Keep-a-Changelog, entries M0–M1.6, deviations recorded
  **[Verified]**.
- **Inconsistencies found [Verified]:**
  1. M1-Decomposition line 100 lists "state_version == max seq" in **M1.6** scope;
     the approved M1.6 execution deferred it to **M1.7** (CHANGELOG M1.6 notes).
     The decomposition was never updated.
  2. ADR-001 §9 repo tree omits `packages/`, `schema/`, `scripts/`, `tests/` —
     approved at M0 but unreflected (frozen-ADR policy means this belongs in an
     addendum note, not an ADR edit).
  3. M1.6 DoD asserted full §Validation-Rules coverage; §8 shows the
     gate-precondition family is not fully covered.
  4. pyproject targets `py311` (ruff) / `python_version = "3.11"` (mypy) while the
     project pins Python **3.12** (`.python-version`) — tools under-target the
     runtime.

---

# 12. Technical Debt

| ID | Severity | Description (evidence) | Recommendation |
|---|---|---|---|
| TD-001 | Low | `Evidence.source` naming (pre-existing, BACKLOG.md) **[Verified]** | Decide at first external release, as planned |
| TD-002 | **Medium** | Four ADR-002 gate-entry precondition rules absent/partial (Enter Planning, Analysis-entry content, Reviewer-entry leaf status, Enter Challenger) — §8 **[Verified]** | Add LIFE-005…LIFE-008 (new frozen ids) as a small M1.6 follow-up or inside M1.7, where transition enforcement naturally lives |
| TD-003 | Medium | Approval-actor rules unenforced: `QualityGate.by` exists but no rule checks approver role or self-approval **[Verified]** | Define actor conventions in M1.7 (events carry `actor`); add GOV rules once writes exist |
| TD-004 | Low–Med | Traceability matrix has no disposition rows for deferred/record-level ADR-002 rules — coverage looks complete when it isn't **[Verified]** | Extend the generator with a static disposition table (rule → covered/record-level/deferred-to-milestone) |
| TD-005 | **Medium** | `get_state()` returns the live mutable aggregate; models unfrozen (facade.py:81-83, core/base.py) **[Verified]** | Resolve in the M1.7 plan: copy-on-read, frozen models, or a documented aliasing contract — required before optimistic locking is meaningful |
| TD-006 | Low | Projection's event-ordering contract (caller supplies seq-order; `seq` ignored) undocumented **[Verified]** | One paragraph in projection.py + Events.md; make the store the ordering authority in M1.7 |
| TD-007 | Low | No event upcasting path despite per-event `schema_version` **[Verified]** | Design at M1.8 (before logs are durable), implement by M1.9 |
| TD-008 | Low | Tooling targets 3.11; runtime pinned 3.12 **[Verified]** | Bump ruff `target-version`/mypy `python_version` to 3.12 |
| TD-009 | Low | M1-Decomposition not updated for the approved M1.6→M1.7 move of `state_version==max(seq)` **[Verified]** | One-line doc fix with the M1.7 commit |
| TD-010 | Low | No validation-benchmark baseline doc (numbers only in test output) **[Verified]** | Add to docs/performance alongside the projection baseline |
| TD-011 | Low | Duplicated analysis-field maps in projection and validation **[Verified]** | Centralize on the third consumer; not before |

---

# 13. Risks Before M1.7

| Risk | Level | Why |
|---|---|---|
| **Optimistic locking built on aliased reads** | **High** | `state_version` checks are meaningless if a reader can mutate the same object the writer projects into: `get_state()` returns the live instance and nothing freezes it **[Verified — §5]**. This is the one issue that can silently corrupt M1.7's core guarantee if unaddressed. It is a *design decision*, not a rework: choose copy/freeze/contract in the M1.7 plan. |
| **Undefined seq semantics** | Medium | `seq` defaults to 0 and is ignored by projection **[Verified]**. M1.7 must define assignment authority, monotonicity enforcement, and duplicate/gap policy before appends exist. Foundations are in place; only the contract is missing. |
| **Owner-exclusive writes have no machine-readable model** | Medium | The ADR-002 R/W matrix exists as prose only **[Verified]**; M1.7's scope includes it (M1-Decomposition:110). Risk is scope-creep into agent concepts that don't exist yet — keep it data (a map), not behavior **[Inference]**. |
| **Persistence of placeholder states** | Low | Empty-log projection yields `EngagementId("")`/`_EPOCH` metadata by design **[Verified]**; M1.8 save should refuse it. One guard, trivially testable. |
| **Replay/snapshot divergence** | Low | Replay-as-composition is already property-tested and `projection_version` policy is written **[Verified]**; M1.9's snapshot-vs-log precedence must reference it, but the groundwork is unusually complete. |
| **Event schema evolution** | Low (now) → Medium (at M1.8) | No upcasting **[Verified]**; harmless while logs are ephemeral, load-bearing the day they persist. |

---

# 14. Go / No-Go Assessment

## **GO** — with two conditions binding on the M1.7 plan.

**Why GO [Verified facts, Inference on sufficiency]:** the architecture the next
three sub-milestones depend on is demonstrably stable. The event catalog matches
the ADR exactly (49/49). Projection is pure, deterministic, and property-tested;
replay-as-composition already holds. Validation is cleanly separated, fully typed,
100%-covered, and extensible without renumbering. The dependency graph is acyclic
and one-directional, there is zero IO inside the state package, and every field
M1.7 needs (`state_version`, `seq`, `actor`, frozen events, typed ids) already
exists with documented semantics. Every deviation from the ADRs found by this
review is either user-approved and recorded, or scheduled future scope — nothing
has silently diverged. Quality gates are green at the reviewed commit.

**Conditions (must be addressed in the M1.7 plan, before code):**
1. **Resolve TD-005 (live-state aliasing).** M1.7's optimistic-concurrency
   guarantee is unsound while `get_state()` aliases the write target. The plan must
   pick copy-on-read, frozen models, or an explicit contract — and say why.
2. **Define the seq/ordering contract (TD-006 + §6 weakness).** Assignment
   authority, monotonicity, duplicate/gap policy, and projection's expectation must
   be written before the append API is designed.

**Scheduled (non-blocking) items:** TD-002 gate-precondition rules and TD-003
approval-actor rules should be folded into M1.7 (where transition/write
enforcement naturally lives) or an explicit follow-up; TD-004 and TD-009/TD-010
are documentation fixes that keep the traceability story honest.

No rework of existing code is required by this review.

---

*Review conducted at commit `962f732` on 2026-07-02. Quality gate (`make check`)
and coverage were executed as part of this review; all file/line references are to
that commit.*
