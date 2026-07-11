# StratAgent 0.1.0-rc2 (RC1.2 sprint) — Release Notes

**RC1.2 — Architecture Convergence Sprint.** Eliminates the architecture
inconsistencies found by the RC1 validation campaign. No new consulting
features; no scope expansion.

## Highlights

- **One framework source of truth.** `knowledge-vault/frameworks/` is now
  canonical for all agents; the plugin's 9 archetype cheat sheets became
  deprecated redirect stubs. (WI-1, [ADR — migration](../../plugins/ruflo-stratagent/knowledge/frameworks/_MIGRATION.md))
- **Live deterministic validation.** Every engagement must pass a blocking
  report gate (`enforce_render_ready` + `validate_consistency`) before a report
  is delivered. No report can bypass validation. (WI-2, [ADR-006](../architecture/ADR-006-Governance-and-Live-Validation.md))
- **Governance gates are mandatory in every mode.** The Reviewer and Challenger
  run on every engagement; "lightweight" now means fewer analysts, never a
  skipped gate. (WI-3, ADR-006)
- **Evidence Provider extension mechanism.** A pluggable interface for sourced
  external evidence — interface, lifecycle, caching, traceability, failure
  isolation — with **no providers populated**. (WI-4, [ADR-007](../architecture/ADR-007-Evidence-Providers.md))

## New packages

- `packages/evidence/` — `EvidenceProvider` Protocol, `ProviderRegistry`,
  `ProviderCache`, provenance-carrying `ProviderResult`.
- `packages/orchestration/` — `run_report_gate` / `enforce_report_gate` /
  `load_state`, plus `scripts/validate_engagement.py`.

## New / changed docs

- New ADRs: ADR-006, ADR-007.
- New: `docs/architecture/Execution-Flow.md`, `docs/guides/DEVELOPER_GUIDE.md`,
  this file, and the migration guide.
- Updated agents/skill: `case-classifier`, `framework-strategist`, `solve-case`
  SKILL (framework source, mandatory gates, Phase-8 gate).

## Quality

- ruff + black + mypy (strict, 80 source files) clean.
- **915 tests pass** (+54 vs RC1's 861): 24 provider-interface, 15 report-gate,
  12 convergence guards, +3 registry edge cases.
- New-package coverage: 98% (`evidence` + `orchestration`).

## Compatibility

- Backwards compatible. The 9 cheat-sheet paths still resolve (as stubs). No
  changes to `state`, `persistence`, `replay`, or `reporting` behaviour. With no
  providers registered, engagement behaviour is identical to RC1.

## Known limitations (unchanged / by design)

- The knowledge vault still ships **no benchmark numbers** (ADR-003 D-6). The
  Evidence Provider seam makes this addressable by configuration, but no
  provider is populated — the platform never invents data.
- LLM engagements remain non-deterministic; the deterministic layer (gate,
  validators, MECE) is what RC1.2 puts on the live path.
