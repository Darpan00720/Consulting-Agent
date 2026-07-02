# Changelog

All notable changes to StratAgent. Format based on
[Keep a Changelog](https://keepachangelog.com). The project is pre-release, so
changes are grouped by implementation milestone under **[Unreleased]** until the
first tagged release.

## [Unreleased]

### M1.7 — Concurrency, Versioning & Corrections — in progress
#### Changed
- **M1.7.2 (design D4) — fold-derived `state_version`; `PROJECTION_VERSION` 1 → 2:**
  `apply()` now unconditionally derives `metadata.state_version` from
  `event.metadata.seq`, making projection the single authority for `state_version`
  (`project(log).metadata.state_version == last event's seq`; `0` for the empty
  log). Because the same previously-valid log now folds to a different state, this
  is the policy-mandated first bump of `PROJECTION_VERSION` (see
  `docs/architecture/projection-versioning.md` §Version history). **Migration:**
  no stored states exist pre-release; re-project any `projection_version = 1`
  state from its log. Projection remains pure, deterministic, and IO-free.
- **M1.7.1 (design D1) — snapshot semantics:** `Engagement.get_state()` now returns
  a **detached deep snapshot** and `Engagement.from_state()` deep-copies on ingest.
  No caller ever holds an alias of the internal state; mutating a snapshot (nested
  models, lists, or the `by_section` dict — anywhere in the object graph) never
  affects the engagement. Signatures unchanged; pre-release behavioral tightening
  of the M1.3-approved intent ("get_state()/snapshot()"), documented in
  `docs/api/EngagementState.md`. Snapshot cost is O(state); benchmarked in M1.7.7.

### M1.6 — Invariants & Validation — 2026-07-02
#### Added
- `state.validation`: state invariant checking **separate from projection**. Rules
  are grouped into five registries — **Structural, Lifecycle, Referential, Business,
  Governance** (ADR-002 §Validation Rules). Each validator is a pure, independent
  `EngagementState -> list[Finding]`; orchestration lives only in the runner.
- First-class `ValidationRule` metadata (rule id, group, `ViolationSeverity`
  = INFO/WARNING/ERROR/FATAL, ADR reference, description, validator) — every rule is
  classified.
- `validate(state)` returns a `ValidationReport` (overall validity, per-severity
  counts, duration, groups checked, violations); `raise_if_invalid` raises
  `StateValidationError` on blocking (ERROR/FATAL) violations. Every `Violation`
  carries rule id, severity, group, path, offending object id (where applicable), and
  a human-readable message.
- Traceability generated from the rule registry into both
  `docs/implementation/traceability-ADR-002.md` and a machine-readable
  `traceability.json` (`make traceability`): one row per rule, **Rule → Validator →
  Test(s)**. Rule ids are a **frozen namespace** — never reused or renumbered.
- Baseline validation benchmarks over small and large Engagement States
  (10 / 100 / 1,000 / 10,000 objects), part of the automated suite.
#### Changed
- Moved `StateValidationError` from `common.errors` into `state.validation` (it now
  carries the `ValidationReport`); `common.errors` keeps only `StratAgentError`.
#### Notes
- Validation is internal (surfaced via the facade in a later milestone). Concurrency,
  versioning, persistence, and replay remain owned by M1.7. 110 tests; validation
  package 100%; green gate.

### M1.5 — Projection — 2026-06-30
#### Added
- `state.projection`: a **pure, deterministic** single-event reducer (`apply`,
  dispatched per event type via `functools.singledispatch` — one reducer per event)
  and `project(events)` as its fold. Replay is the composition of `project`, not a
  separate algorithm. Projection performs no validation and no IO. Internal module.
- `projection_version` on `EngagementState`; `PROJECTION_VERSION` stamps projected
  states.
- Baseline projection benchmarks (`pytest-benchmark`) at 10 / 100 / 1,000 / 10,000
  events, part of the automated suite.
#### Changed
- **ADR-002 implementation correction:** added the §2 lifecycle-audit fields to
  `EngagementState` — `phase_history`, `quality_gates`, and `pending_requirements`
  (broadened from the ADR's `blocked_on` to cover both execution blockers and
  missing information) — with models `PhaseRecord`, `QualityGate`,
  `PendingRequirement` and enums `GateResult`, `PendingKind`.
- `project(events)` always returns an `EngagementState` (empty log → empty state) —
  no `Optional`.
- `EngagementCreated.created_by` tightened to `Literal["human", "system"]` for
  consistency with `EngagementMetadata`.
#### Notes
- Determinism is guaranteed: objects created during projection derive their ids and
  timestamps from the event — never minted fresh. 71 tests; projection 99%; green gate.

### M1.4 — Event Model + Identifier Harmonization — 2026-06-30
#### Added
- Event model: `EventMetadata` (business `occurred_at` + system `recorded_at`;
  `actor` vs `source`; `schema_version`; `causation_id`/`correlation_id`),
  `EventSource`, `EventCategory` (every event maps to exactly one), `EventType`, and
  the frozen, immutable, self-contained event catalog as a discriminated `Event`
  union. Documented in `docs/api/Events.md`.
- Strongly-typed identifiers (`EventId`, `EngagementId`, `EvidenceId`, `AssumptionId`,
  `GapId`, `IssueNodeId`, `FrameworkId`, `DeliverableId`, `RecommendationId`) in
  `state.identifiers`.
#### Changed
- **Controlled API refinement (pre-external-release):** addressable domain models now
  use their strongly-typed ids (`Evidence.id: EvidenceId`,
  `EngagementMetadata.engagement_id: EngagementId`, etc.), aligning the domain and
  event layers. Schema-compatible (typed ids serialize as strings) — a documented
  refinement, not a breaking change.

### M1.3 — Engagement State Facade — 2026-06-30
#### Added
- `Engagement` facade — the sole public entry point — with a **frozen** six-method
  API (`create`, `from_state`, `from_json`, `get_state`, `validate`, `to_json`).
  State is reached via `get_state()` (accessor, not a public attribute) and evolves
  only through the event API (later); no mutation methods are exposed.
- `EngagementProtocol` describing the facade contract, so file-backed / AgentDB /
  testing implementations can be substituted without changing consumers.
- Curated public surface: `state.__all__` re-exports the facade, protocol, models,
  enums, and value objects; internals are not exported (guarded by an
  export-surface test).
#### Notes
- No new domain fields or behavior beyond create/read/validate/serialize.
- The Engagement State public API (`docs/api/EngagementState.md`) is declared **Stable**.

### M1.2 — Engagement State Section Models & Aggregate — 2026-06-30
#### Added
- All ADR-002 §3–§25 section models (scoping, planning, analysis, governance,
  output) and the full `EngagementState` aggregate — valid with only `metadata`
  (every other section Optional or an empty collection).
- `common` value objects: `ConfidenceScore` (validated [0, 1]), `Identifier` /
  `Reference` aliases, and a `DomainObject` base providing an immutable
  auto-generated `id` plus optional `created_at/updated_at/created_by/updated_by`
  audit metadata.
- Extensible enums (`OTHER`/`UNKNOWN` where taxonomies are open).
- Section-coverage test tracing every ADR-002 §3–§25 section to an
  `EngagementState` field.
#### Changed
- Refactored `Evidence`/`Assumption` onto `DomainObject` + `ConfidenceScore`
  (behavior unchanged; M1.1 tests remain green).
- Regenerated `schema/engagement-state.schema.json` from the full models.
#### Notes
- Models only; events / projection / invariants / persistence / facade remain
  later M1 sub-milestones. 36 tests; state coverage 99%; quality gate green.

### M1.1 — Evidence & Assumption Ledgers — 2026-06-30
#### Added
- `state.Evidence` and `state.Assumption` record models (ADR-002 §9, §14) with
  record-level validation.
- Modular per-evidence-type validation registry — new evidence types register a
  rule without modifying the model validator.
- `pytest-cov` and the `make cov` coverage target.
- `docs/implementation/M1-Decomposition.md` (9 sub-milestone plan); this changelog;
  and `docs/implementation/BACKLOG.md` (technical-debt tracker).
#### Notes
- Record-level validation only; aggregate / referential / event / persistence logic
  is deferred to later M1 sub-milestones.
- State coverage 99% (ledgers 100%); 26 tests passing; quality gate green.

### M0 — Engineering Foundation — 2026-06-30
#### Added
- Local git repository; uv + Python 3.12 (pinned); Ruff, Black, MyPy (strict),
  Pytest, pre-commit; `.editorconfig`, `.env.example`, shared logging.
- Capability-based `packages/` layout (`core`, `common`, `state` populated;
  `knowledge`, `planning`, `analysis`, `governance`, `reporting` scaffolded).
- Foundational Engagement State slice (`EngagementMetadata`, `LifecycleStatus`) with
  JSON Schema generated from Pydantic + a drift test.
- Architecture v1.0 (ADR-001–005) and the implementation roadmap.
