# Changelog

All notable changes to StratAgent. Format based on
[Keep a Changelog](https://keepachangelog.com). The project is pre-release, so
changes are grouped by implementation milestone under **[Unreleased]** until the
first tagged release.

## [Unreleased]

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
