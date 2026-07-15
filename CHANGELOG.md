# Changelog

All notable changes to StratAgent. Format based on
[Keep a Changelog](https://keepachangelog.com). The project is pre-release, so
changes are grouped by implementation milestone under **[Unreleased]** until the
first tagged release.

## [Unreleased]

_No unreleased changes beyond 1.0.0-beta.1 below._

## [1.0.0-beta.1] — 2026-07-15

First beta of the **public web dashboard** (`apps/dashboard/`), which is now the
primary shipping product alongside the Claude Code plugin. The reference core
(`packages/`) remains a frozen, separately-tested library — see
`docs/architecture/ADR-008` for how the three artifacts relate.

### Added
- **Multi-provider free-tier chain** (`apps/dashboard/backend/app/pipeline/providers.py`):
  Gemini → Cerebras → OpenRouter → GitHub Models → Cloudflare Workers AI, each
  joining only when its key is present. **Multiple keys per provider** (comma or
  numbered) with per-key pacing and failover.
- **Auto-resume on rate-limit exhaustion**: engagements checkpoint completed
  phases/analysts to the event log, pause with a live countdown, and resume from
  the last completed step — no work lost, no manual re-run.
- **Restart recovery**: engagements orphaned by a server restart are adopted at
  startup (free-tier resumes; BYOK closes honestly since the key is never stored).
- **Multimodal input**: paste charts/screenshots into the case brief; forwarded
  to vision-capable providers, never persisted.
- **Apple-grade engagement page**: staged stepper, per-analyst progress,
  governance panel, auto-resume banner.
- **CI** (`.github/workflows/ci.yml`) gating both test suites, lint, format, and
  types; issue/PR templates.

### Changed
- **Groq removed from the free chain** (6k TPM can't fit a reconcile prompt);
  a paid `gsk_` key is still accepted as BYOK.
- Dashboard held to the same `ruff` + `black` bar as the core.

### Fixed
- Docker SQLite persistence (volume path never matched the DB path — every
  redeploy silently wiped history).
- Rate-limit classification hardened (413-as-rate-limit, reasoning-token
  starvation, exponential resume backoff with jitter, cap-after-jitter).

## [0.1.0-rc2] — 2026-07-10

### Repository finalization (open-source release candidate) — docs only
No code, agents, architecture, or consulting logic changed.
- **Added the standard OSS files:** root `README.md` (world-class homepage),
  `LICENSE` (MIT), `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` (Contributor Covenant
  2.1), `SECURITY.md`, `ROADMAP.md`, `CITATION.cff`, `ACKNOWLEDGEMENTS.md`,
  `SUPPORT.md`, `FAQ.md`.
- **Refreshed the stale plugin README** (`plugins/ruflo-stratagent/README.md`)
  to the current system: full lifecycle, 16 agents, vault-canonical framework
  store, governance/validation/telemetry, `0.1.0-rc2`.
- **Fixed stale references in `CLAUDE.md`** (framework store → vault; agent
  count/list → 16).
- **Added** `docs/release/Repository-Release-Report.md` (release report +
  documentation audit + cleanup report + repository score).

### Observability — telemetry integration (live path) — added
Wires the telemetry foundation into the live engagement path. Instrumentation
only; no consulting logic, agent, or architecture changes.

- **`telemetry.EngagementTracer`** — per-engagement facade (spans, rework,
  phase markers, analytics) over a JSONL sink + in-memory mirror.
- **`orchestration.telemetry`** — Python emission bridge: `record_gate` /
  `instrument_gate` (validation-gate event), `record_governance` (reviewer/
  challenger verdicts), `content_metadata` / `unsupported_finding_count` derived
  from `EngagementState`.
- **CLIs** — `scripts/record_telemetry.py` (the markdown orchestrator's Bash
  bridge to append a span), `scripts/engagement_telemetry.py` (analytics / OTLP
  export), `scripts/replay_pilots.py` (pilot replay → sample traces).
- **SKILL** — `solve-case` now records a span per dispatch (additive telemetry
  section; consulting instructions unchanged).
- **Benchmark** — the 3 pilots replayed from real observed run logs into
  `docs/observability/samples/*.jsonl`; analytics verified (Northwind 15 spans,
  Halberd rework=1, quality: reviewer pass 1.0 / challenger intervention 1.0 /
  needs-rework 0.2).
- **Tests:** +16 (integration, replay, parallel-execution, CLI round-trip);
  954 total passing. **Docs:** samples README, integration API, updated plan +
  quickstart.

### Observability & Analytics layer — added
Additive operational telemetry; no architecture, agent, or consulting-logic
changes. Sits alongside (does not duplicate) the ADR-002 domain event log.

- **`packages/telemetry/`** — canonical `TelemetryEvent` schema (frozen,
  JSON/JSONL, OTel-compatible via `to_otlp()`); pluggable sinks (`JSONLSink`
  append-only, `MemorySink`, `NullSink`, `MultiSink`); `Recorder` (`emit` +
  timed `span`, sampling, metadata redaction); pure analytics
  (`engagement_analytics`, `quality_analytics`, `summarize_confidence`).
- **Tests:** +23 (`tests/telemetry/`), 96% package coverage; 938 total passing.
- **Docs:** `docs/observability/` — architecture, event schema, analytics
  definitions, dashboards (Engineering/Product/Research/Operations), API
  contracts + examples, retention/privacy, implementation plan.
- **`pyproject.toml`** — registered `telemetry` as first-party.
- Integration into the live orchestration is **designed, not wired** (agents are
  markdown prompts); Phases 1–4 in the implementation plan.

### RC1.2 — Architecture Convergence Sprint — complete
Resolves the architecture inconsistencies found by the RC1 validation campaign.
No new consulting features.

#### Added
- **`packages/evidence/`** (WI-4, ADR-007) — Evidence Provider extension
  mechanism: `EvidenceProvider` Protocol, `ProviderRegistry` (failure isolation,
  per-call timeout, traceability), `ProviderCache` (TTL, deterministic keys),
  provenance-carrying `ProviderResult`. No providers populated.
- **`packages/orchestration/`** + **`scripts/validate_engagement.py`** (WI-2,
  ADR-006) — live deterministic report gate; blocks report delivery unless
  `enforce_render_ready` + `validate_consistency` pass, with actionable
  diagnostics.
- **ADR-006** (mandatory gates + live validation), **ADR-007** (evidence
  providers).
- **Docs:** `Execution-Flow.md`, `DEVELOPER_GUIDE.md`, RC1.2 release notes +
  migration guide.
- **Tests:** +54 (provider interface, report-gate, convergence guards).

#### Changed
- **Framework source of truth (WI-1):** `knowledge-vault/frameworks/` is now
  canonical. The 9 plugin cheat sheets became deprecated redirect stubs; added
  `knowledge/frameworks/_MIGRATION.md`. `case-classifier`, `framework-strategist`,
  and the `solve-case` SKILL repointed to the vault.
- **Mandatory governance (WI-3):** removed the SKILL's skip-Reviewer rule;
  Reviewer + Challenger run in every mode. SKILL Phase 8 now runs the live gate.
- **`pyproject.toml`** — version → `0.1.0-rc2` (RC1.2 sprint); registered
  `evidence` + `orchestration` as first-party.

#### Unchanged
- `packages/state`, `persistence`, `replay`, `reporting` behaviour;
  `knowledge-vault/` note content. Engagement behaviour identical with no
  providers registered.

## [0.1.0-rc1] — 2026-07-09

### M9 — Production Readiness — complete
#### Added
- **`knowledge-curator.md`** (new agent) — post-engagement vault write-back:
  extracts up to 3 durable, generalizable insights from a completed engagement
  and writes them as `status: draft` notes to `knowledge-vault/`. ADR-005
  compliant (writes only to vault, never to state or engagements/).
- **`docs/guides/QUICKSTART.md`** — 5-minute setup guide.
- **`docs/guides/USER_GUIDE.md`** — complete 10-phase workflow documentation.
- **`docs/reviews/RC1-Release-Notes.md`** — release notes for 0.1.0-rc1.
- **`engagements/acme-profitability-demo/`** — demo engagement artifacts for a
  profitability case (intake, report).

#### Updated
- **`report-writer.md`** — ADR-005 compliance section: documents exactly which
  state sections this agent owns (recommendations, confidence, deliverables).
- **`solve-case/SKILL.md`** — full 10-phase lifecycle including all M4-M6 agents
  (information-gap, planner, framework-selector, issue-tree-generator,
  strategy-analyst, risk-analyst, reviewer, challenger, knowledge-curator).
- **`pyproject.toml`** — version bumped to `0.1.0-rc1`.

### M8 — Evaluation & Validation — complete
#### Added
- **`tests/fixtures/golden_state.py`** — `make_golden_profitability_state()`:
  fully-populated, governance-cleared EngagementState for integration tests.
  7 issue-tree nodes, 3 evidence records, 1 load-bearing assumption with
  breakeven, 2 analysis blocks, reviewer approved, challenger stands_with_caveats.
- **`tests/integration/test_engagement_lifecycle.py`** (94 tests) — full state
  machine, rework loops, forbidden shortcuts, terminal state guard, governance
  gate preconditions, golden-state assertions.
- **`tests/integration/test_report_generation.py`** (38 tests) — all 13 section
  headers, metadata, evidence/assumption citations, assumption labeling,
  recommendation body, challenger section, footer, graceful empty-section handling.
- **`tests/validation/test_structural_validation.py`** (30 tests) — all 4
  check_render_ready rules, enforce_render_ready, consistency validation,
  five-section coverage, golden state passes all validators.
- **`tests/perf/test_m7_bench.py`** — M7 performance baselines:
  `render_report` cold ~82µs, warm ~22µs; `check_render_ready` ~3µs.

### M7 — Report Generation — complete
#### Added
- **`packages/reporting/renderer.py`** — `render_report(state) → str`, pure
  function, deterministic, 14 sections. Evidence-backed findings cited inline;
  assumption-only findings labeled `[ASSUMPTION: ...]`; footer includes gate
  verdicts and UTC timestamp.
- **`packages/reporting/validation.py`** — `check_render_ready(state)` (4 rules:
  REVIEWER_GATE_NOT_RUN/APPROVED, CHALLENGER_GATE_NOT_RUN/CLEARED,
  UNEVIDENCED_FINDING, ASSUMPTION_NO_BREAKEVEN), `enforce_render_ready(state)`,
  `validate_consistency(state)` (INCOMPLETE_ANALYSIS_BLOCK).
- **`packages/reporting/__init__.py`** — 8-symbol public API: `render_report`,
  `check_render_ready`, `enforce_render_ready`, `validate_consistency`,
  `engagement_summary`, `ReportRenderError`, `ValidationIssue`, `ValidationReport`.

### M4–M6 — Consulting Intelligence — complete
#### Added
- **M4 — Planning:** `mece_validator.py`, `preconditions.py` (4 gate-check
  functions), 4 new agent files (information-gap, planner, framework-selector,
  issue-tree-generator). 37 new tests.
- **M5 — Analysis:** `analysis/contracts.py` (validate_analysis_block, 4 rules,
  ANALYST_SECTION_OWNERS), 2 new agent files (strategy-analyst, risk-analyst).
  16 new tests.
- **M6 — Governance:** `governance/gates.py` (6 gate functions), `transitions.py`
  (full ADR-002 state machine, 3 rework loops), 2 new/updated agent files
  (reviewer, challenger updated to ADR-005). 50 new tests.

### Prior milestones (M1–M3)
See full history in the pre-release milestone history below.

## Pre-release milestone history (M0–M6)

### M2 — Knowledge Library (Obsidian vault + validator) — complete
#### Added
- **`packages/knowledge`** — a new leaf package: the knowledge-vault frontmatter
  validator. Pure, read-only, 100% covered (260/260). Public surface (frozen,
  28 symbols, pinned in `tests/knowledge/test_api_freeze.py`):
  - **`parse_frontmatter(text)`** — extracts and parses the leading YAML
    frontmatter block; raises `FrontmatterError` on missing, unterminated,
    invalid, or non-mapping frontmatter.
  - **`validate_note(text)`** — validates one note against the typed schema
    (ADR-003 §5 common header + ADR-004 §3 for `framework` notes); dispatches
    by `type` across all 13 note types.
  - **`validate_vault(vault_dir)`** — vault-wide validator: per-note frontmatter
    via `validate_note`, plus broken `[[wikilinks]]`, circular self-links,
    duplicate `id`s and aliases, ADR-004 domain coverage, and missing category
    directories. Collect-all; never fail-fast.
  - **13 typed frontmatter models** (`CommonHeader` and 12 per-type subclasses)
    + 5 enums (`NoteType`, `NoteStatus`, `Visibility`, `FrameworkTier`,
    `DeliverableKind`) + `VaultReport` / `ValidationIssue` / `ValidationSeverity`.
  - `packages/state`, `packages/persistence`, `packages/replay` **zero-diff**
    across the whole milestone. Architecture v1.0 frozen and unmodified.
- **`knowledge-vault/`** — 132 draft vault notes (all `status: draft`, Hybrid D-6
  authorship policy; reviewer-promotion pending). Breakdown by type:
  - 15 `domain` notes — ADR-004 §2 consulting domains
  - 63 `framework` notes — ADR-004 §3 (15 primary + 48 supporting)
  - 15 `issue_tree` notes — ADR-004 §4 MECE issue trees
  - 15 `business_problem` notes — ADR-004 §8 business problems
  - 14 `kpi` notes — ADR-004 §5 canonical KPI catalog (generic definitions
    only; no benchmark values — reviewer-supplied per D-6)
  - 10 `industry` notes — ADR-004 §6 industry knowledge model (structure,
    drivers, engagements; no benchmarks/averages)
  - validate_vault: **132 notes, is_valid=True, 0 errors, 3 advisory warnings**
    (deliverables/, prior-cases/, recommendations/ not yet populated)
- **Docs:** `docs/api/Knowledge.md` (public API reference),
  `docs/reviews/M2-Completion-Report.md`,
  `docs/architecture/knowledge-layer.md` (addendum; v1.0 stays frozen).
- **Delivered across five approval-gated slices** — design (`31e3dbe`), S1
  validator core (`38bc42e`), S2 vault-wide validator (`f7adf9a`), S3 domain +
  primary framework notes (`d9b9ac9`), S4A supporting frameworks + issue trees +
  business problems (`c8f6020`), S4B KPI + industry catalog (`ce6deb8`),
  S5 finalization (this commit). See `docs/implementation/M2-Design.md` (PROPOSED).
- **Open decisions deferred to M3/standalone review:** D-3 (plugin cheat-sheet
  migration), D-4 (ADR-003/004 ratification to `Accepted`), D-5 (draft-gate
  enforcement), D-8 (per-type schemas for 5 ADR-004-added types), D-9
  (per-note `schema_version`).

### M1.9 — Replay Engine (replay & recovery) — complete
#### Added
- **`packages/replay`** — a new sibling package that rebuilds engagements from
  event logs. Pure orchestration over frozen seams; `packages/state` and
  `packages/persistence` are **zero-diff** across the whole milestone, and
  `verify_log`/`verify_pair`/`project`/`AppendPipeline`/`make_committed`/
  `EngagementStore` are unchanged. Public surface (frozen, 6 names):
  `ReplayEngine`, `ReplayContract`, `replay`, `recover`, `ReplayError`, and the
  re-exported frozen `ReplayIntegrityError`.
  - **`replay(log)`** rebuilds an append-capable `Engagement` via the single
    fixed pipeline `verify_log → project → verify_pair → AppendPipeline(…,
    append_supported=True)` (`make_committed` runs transitively; no alternate
    path, no mutation, no fabrication, no repair — RP-001, RP-017).
  - **`recover(log, snapshot)`** rebuilds from a persisted `(log, snapshot)`
    pair; a valid pair rebuilds from the snapshot, a `PROJECTION_STALE` pair is
    upgraded by whole-log re-projection (the only migration mechanism). Recovery
    never writes persistence, mutates the snapshot, or suppresses integrity
    failures; persisting an upgraded snapshot is the caller's job via
    `EngagementStore.save` (DD-7 no-autosave preserved).
  - **Errors:** `ReplayError` is an additive orchestration-only base (no new
    codes); integrity defects surface as the frozen `ReplayIntegrityError`.
  - **Invariants RP-001…RP-034** (replay contract, purity, determinism,
    fold-equivalence, recovery, property/stress, benchmarks) — see
    `docs/reviews/M1.9-Completion-Report.md`. Replay package **100% covered**.
- **Docs:** `docs/api/Replay.md` (public API reference),
  `docs/reviews/M1.9-Completion-Report.md`, `docs/architecture/replay-layer.md`
  (records replay as an implemented layer; Architecture v1.0 stays frozen),
  replay baselines in `docs/performance/baselines.md`.
- **Delivered across seven approval-gated phases** — design (`c61df51`),
  skeleton (`d894266`), replay (`b244afb`), recovery (`54d67b8`), property/stress
  suite (`252f428`), benchmarks (`e483296`), finalization (Phase 7). See
  `docs/implementation/M1.9-Design.md` (APPROVED).

### M1.8 — Persistence (append / save / load) — complete
#### Added
- **M1.8-S5 — persistence finalization** (docs / API-freeze / benchmarks /
  integration; **no behavioural change**). Froze the public surface at exactly
  seven names (`EngagementStore` + the six error types) with pinned
  `EngagementStore` method signatures (`tests/persistence/test_api_freeze.py`).
  Added end-to-end integration tests (`test_integration.py`):
  save→load→append→save continuity, N-cycle byte-identical determinism
  (PER-011), a process-restart simulation (fresh `EngagementStore` on the same
  root stays append-capable, PER-007), and the canonical-projection invariant
  (persisted snapshot `== project(log)`, `verify_pair` always passes). Added
  `save`/`load`/checksum-verification benchmarks (`tests/perf/test_m1_8_bench.py`)
  under the existing cold-run methodology, recorded in
  `docs/performance/baselines.md`. New public API reference
  `docs/api/Persistence.md` states explicitly that **persistence stores
  canonical projected snapshots rather than runtime incremental state** and why
  `verify_pair` therefore always succeeds for persisted artifacts. Persistence
  package coverage 100%; `packages/state` zero-diff. See the
  [M1.8 Completion Report](docs/reviews/M1.8-Completion-Report.md).
- **M1.8-S4 — `EngagementStore` (save/load orchestration)** (`persistence/store.py`,
  public): composes `format` + `atomic` + `verify_log`/`verify_pair` +
  `project` + `AppendPipeline` — never duplicating them. **save** (read
  committed log → build canonical snapshot `project(log)` → SHA-256 → serialize
  → atomic-write `events.log` → `state.json` → `manifest.json`, manifest last as
  the commit marker); **load** (read manifest → state → log → verify checksums →
  decode → `verify_log` → `verify_pair` → reconstruct an append-capable
  `Engagement`; no replay, no repair, no reprojection). The store exclusively
  owns directory creation and SHA-256 (only `store.py` imports `hashlib`;
  source-scan tested, incl. `packages/state/**`). Errors mapped:
  missing→`MissingArtifactError`, malformed/checksum→`CorruptArtifactError`,
  unsupported version→`IncompatibleVersionError`, missing/partial
  manifest→`TornWriteError`; unexpected `OSError` wrapped (never leaked).
  Deterministic (PER-011: `save(load(save(E)))` byte-identical) and
  no-partial-visibility (PER-012: interrupted save is never loadable). Reads the
  committed log via the approved `_pipeline` seam (P-DD-A). Invariants
  S4-1..S4-16.
  - **Canonical persistence representation (M1.8-S4 projection decision).** The
    persisted snapshot is the canonical projection `project(log)`, **not** the
    runtime `committed.state`. Runtime incremental state is an implementation
    detail: `apply` stamps only `state_version` and inherits `projection_version`
    from `create` (0), so a live snapshot carries stale projection provenance.
    Save normalizes the snapshot through the projection engine
    (`projection_version` → `PROJECTION_VERSION`) so every persisted
    `(log, snapshot)` pair satisfies `verify_pair` on load with no replay or
    repair. The contract preserves the event log, domain state, version, and
    append capability exactly — **canonical engagement semantics** — normalizing
    only projection provenance. `verify_pair` remains frozen and unchanged; no
    bypass, no relaxation of replay integrity. S4-16 permanently documents this.
- **M1.8-S3 — atomic filesystem primitives** (`persistence/atomic.py`, internal;
  the sole IO-authority module): `atomic_write` (temp → flush → fsync →
  `os.replace` → dir fsync — atomic visibility, PER-015; byte-exact, PER-017),
  `append_bytes` (durable append + fsync, for the event log), `read_bytes`
  (absent → `MissingArtifactError`). Works **only in bytes** — no
  serialization, no hashing, no engagement construction. It is the **only**
  persistence module permitted to `replace`/`rename`/`fsync`/create temp files
  (PER-016, source-scan tested). On any pre-commit failure the target is
  untouched and no stray temp remains.
- **M1.8-S2 — persistence codec** (`persistence/format.py`, internal; pure): the
  on-disk format — `dump_log`/`load_log` (NDJSON, one `Event` per line, seq
  order), `dump_snapshot`/`load_snapshot` (`EngagementState` JSON), and a minimal
  frozen `Manifest` (`format_version`, `log_sha256`, `snapshot_sha256` — no
  timestamps/UUIDs/paths; deterministic, preserving PER-011) with
  `dump_manifest`/`load_manifest`. **Pure** (PER-013): no filesystem IO, no
  hashing (the store supplies checksums), no globals/mutation/caching.
  **Canonical** (PER-014): equivalent objects serialize identically. Malformed /
  schema-invalid input raises `CorruptArtifactError` (codec owns malformed JSON).
- **M1.8-S1 — persistence package skeleton** (`packages/persistence/`, sibling to
  `state`; DD-1 keeps `state` IO-free): the persistence **error taxonomy**
  (`PersistenceError(StratAgentError)` + `MissingArtifactError` / `TornWriteError`
  / `CorruptArtifactError` / `IncompatibleVersionError`, each with a stable
  `PersistenceErrorCode`) and the **storage-layout constants** (`paths.py` —
  `engagements/<slug>/{events.log,state.json,manifest.json}`, constants only,
  no IO). Public surface is only the error taxonomy; `EngagementStore` and
  save/load arrive in later slices. `engagements/*/` gitignored (P-DD-C, README
  kept). No IO, no serialization, no store yet.

### M1.7 — Concurrency, Versioning & Corrections — complete (2026-07-04)
Writable Engagement State: snapshot semantics, the append pipeline + facade
event API, replay integrity, gate-entry validation rules, ownership as data,
and performance baselines. Sub-milestones M1.7.1–M1.7.8; see
`docs/reviews/M1.7-Completion-Report.md`.
#### Added
- **M1.7.8 — M1.7 closure** (docs/tooling/hygiene only; no runtime change):
  tooling aligned on Python 3.12 (TD-008; `_replace` adopts a PEP 695 generic,
  UP040 type-aliases deferred as TD-012); M1-Decomposition §M1.7 corrected to
  the as-built structure (TD-009); BACKLOG reconciled as the authoritative TD
  register (TD-003→M6, TD-007→M1.8 recorded); M1.7 Completion Report added.
- **M1.7.7 — performance baselines** (measurement + docs only; no behaviour
  change): benchmarks for the append write path (`append_event`,
  `append_events`), the `get_state` snapshot, and replay verification
  (`verify_log`, `verify_pair`) in `tests/perf/test_m1_7_bench.py`, plus a
  `make bench` target. One consolidated `docs/performance/baselines.md` now
  records projection, validation, append, snapshot, and replay baselines with a
  fresh environment block, complexity, interpretation, and limitations — the
  M1.5 `projection-baseline.md` is retained for history and points to it.
  **Closes TD-010** (the validation baseline was published only in test output).
  Reuses the established single-run `pedantic` methodology (10/100/1k/10k);
  baselines are regression references, never gates — no benchmark asserts a
  latency threshold. Confirmed the design's headline claims: `append_event` is
  validation-dominated and log-independent (~1 ms at 10k objects), `get_state`
  is the O(state) deep-copy price of snapshot isolation (~73 ms at 10k),
  replay verification is cheap and linear (~1.6–1.8 ms at 10k events).
- **M1.7.6 — ownership matrices as data** (`state/ownership.py`, internal — no
  enforcement, no public-API change): `Role` (ADR-005 names + externals +
  ADR-002 collective markers; seeds M6's role registry), `COMPONENT_OWNERSHIP`
  (16 components; exactly one writer per writable resource, pairwise-disjoint,
  every row evidenced + mapped to its future enforcement owner),
  `SECTION_OWNERSHIP` (the ADR-002 Agent Read/Write Matrix transcribed
  verbatim, mapped onto all 30 `EngagementState` fields — drift-tested), and
  `EVENT_OWNERSHIP` (all 49 event types → writing roles → affected sections,
  from the ADR-002 event catalog — drift-tested against `EventType`). The
  traceability generator now emits the three datasets (markdown + JSON
  `ownership` key). Completeness/fidelity tests fail on any unmapped event
  type, unmapped state field, duplicate writer, or ADR drift. Enforcement
  remains deliberately absent until M6 (TD-003).
- **M1.7.5 — remaining validation rules + traceability dispositions (closes
  TD-002, TD-004):** four gate-entry precondition rules in the existing
  lifecycle registry — `LIFE-005` (planning+: classification, real question,
  load-bearing gaps answered/assumed), `LIFE-006` (analysis+: non-empty issue
  tree + plan), `LIFE-007` (review+: every leaf answered), `LIFE-008`
  (challenge+: reviewer verdict approved) — with **at-or-beyond** semantics and
  COMPLETED/FAILED/ABORTED exempt (an implementation inference; ADR-002 is
  silent on ended engagements). The append pipeline now enforces these at write
  time automatically (it validates every candidate post-state). Traceability
  gains a **disposition section** (markdown + JSON): all 25 ADR-002
  §Validation-Rules items mapped exactly once across registry / record-level /
  boundary-write / boundary-at-rest / by-construction / deferred, guarded by
  completeness tests. "No mutation after completed" is recorded as an
  append-boundary admission policy owned by **M1.8** — deliberately not
  snapshot validation. Rule registry: 17 → 21 rules.
- **M1.7.4 — replay integrity** (`state/append/integrity.py`, internal — no
  public API change): `verify_log` / `verify_pair`, the at-rest counterpart of
  the write-time guard — pure, single-pass, first-failure-with-index. Enforces
  R1–R18: 1-based contiguous ordered seqs, no unassigned events, event-id
  uniqueness, **required genesis** (`EngagementCreated` first, exactly once — no
  recovery), **aggregate completeness** (every event anchored to the genesis
  `engagement_id`; empty ids rejected), and paired-snapshot checks
  (`state_version == last seq` — also how truncation surfaces, since a truncated
  log is provably undetectable alone; engagement identity;
  `projection_version` compatibility). `ReplayErrorCode`: 13 stable codes in an
  additive-frozen namespace; hierarchy `SequenceIntegrityError` /
  `LogIdentityError` / `SnapshotMismatchError` under
  `ReplayIntegrityError(StratAgentError)` — deliberately **not** `AppendError`.
  **Fatal** (replay must not begin) vs **recoverable** (operator action):
  only `projection_stale` is recoverable — discard snapshot, re-project the
  verified log. Schema evolution/upcasting deferred to M1.8 (TD-007).
  Consumers arrive in M1.8 (load) and M1.9 (replay).
- **M1.7.3-S1 — append contract primitives** (`state/append/`, internal until S5):
  error hierarchy `AppendError` → `VersionConflictError` (expected/actual) and
  `EventAdmissionError` (reason/event_id), each carrying a stable machine-readable
  `error_code` (`AppendErrorCode`, a frozen namespace — messages are human-readable,
  never a contract); `AppendResult` (frozen, JSON-serializable both ways):
  `success`, `version`, `projection_version` (self-describing projection
  semantics), `first_seq`, `last_seq`, `appended`, `warnings`.
- **M1.7.3-S2 — sequence stamping + version derivation** (pure, stateless
  arithmetic): `sequencing.stamp(events, first_seq)` returns contiguous-seq
  frozen copies and accepts **only unassigned events** (`seq == 0`; re-stamping
  rejected); `versioning.current_version / current_sequence / next_state_version`
  derive exclusively from `event.metadata.seq` (never payloads), with
  `next_state_version == current_sequence` making the D2↔D4 identity explicit.
  Precondition violations raise `ValueError` (programmer errors) — `AppendError`
  stays reserved for the public append API. 18 dedicated invariant tests
  (A1–A8, V1–V7, C1–C3). These modules are arithmetic only; correctness is
  established by S3 admission, the S4 pipeline, and M1.7.4 replay integrity.
- **M1.7.3-S6 — append API completion & freeze** (no new behavior; M1.7.3 done):
  full event-API documentation in `docs/api/EngagementState.md` (all ten facade
  operations, append contracts, optimistic concurrency, the three version
  numbers, the temporary read-only table, lifecycle diagram) and the sequence
  contract in `docs/api/Events.md` (seq-0 sentinel, allocator authority,
  ordering source of truth, idempotency). Edge-case tests S6-1…S6-8 (already-
  covered cases reference F4/F5) and a **final public-API freeze test** pinning
  the ten Engagement methods, `state.__all__`, `AppendResult` fields, the
  `AppendError` hierarchy, the `AppendErrorCode` namespace, and the
  `ValidationReport` surface — any future surface change requires a conscious
  test edit.
- **M1.7.3-S5 — facade event API** (wiring layer only): `Engagement` gains
  `append_event`, `append_events`, `current_version` (reads the stored
  S2-computed committed version), and `current_sequence` (delegates to S2);
  `validate()` now returns the M1.6 `ValidationReport` unaltered (design D5);
  `EngagementProtocol` extended in lockstep. Public exports added: the append
  result/error contracts (`AppendResult`, `AppendError`, `AppendErrorCode`,
  `VersionConflictError`, `EventAdmissionError`, `AppendUnsupportedError`) and
  the validation surface (`ValidationReport`, `Violation`, `ViolationSeverity`,
  `ValidationGroup`, `StateValidationError`). **Temporary append availability
  (P24):** `create()` → append supported; replay (M1.9) → supported;
  `from_state()`/`from_json()` → **read-only** — appends raise
  `AppendUnsupportedError` (stable code `append_unsupported`) before any
  pipeline phase executes, because a log-less adopted state must never
  fabricate sequence numbers or reset versions. The pipeline knows its
  capability explicitly (`append_supported`, supplied by the facade's
  provenance — never inferred from state/versions/log contents). This
  restriction is temporary: M1.8 persisted logs and M1.9 replay remove it.
  Invariants F1–F10 + P24, one dedicated test each.
- **M1.7.3-S4 — atomic append pipeline + commit point** (orchestration only):
  `AppendPipeline.append_event / append_events` run the **fixed contractual
  phase order — Decision → Allocation → Projection → Validation → Commit** —
  composing S3's guard, S2's arithmetic, M1.7.2's `apply`, and M1.6's runner
  with zero logic of its own (P17: no arithmetic; P19: no business rules).
  `Committed` (log, state, event_ids, stored S2-computed `version`) is the
  exactly-one immutable committed-state object; **`make_committed()` is its
  only construction path** (pure/referentially transparent — P22/P23; replay,
  persistence, restore, and recovery are future consumers). `CandidateCommit`
  (log, state, event_ids, validation_report, **events** = the stamped batch)
  is the complete commit payload M1.8 will persist. Commit gate = severity
  semantics (ERROR/FATAL counts; INFO/WARNING never block, surfaced in
  `AppendResult.warnings`). Failed appends leave the snapshot byte-identical
  and consume no sequence numbers; commits happen exactly once
  (`StateUpdater` = `make_committed` + one reference swap). 23 dedicated
  invariant tests (P1–P23) incl. a reusable `SpyStateUpdater` for M1.8.
- **M1.7.3-S3 — concurrency guard** (pure, stateless decision layer):
  `guard.check_append(candidates, *, engagement_id, committed_version,
  committed_event_ids, expected_version) -> GuardDecision` — admission checks
  (empty batch; engagement match incl. mixed batches; `seq == 0` sentinel;
  committed-id idempotency; intra-batch id uniqueness) then the O(1) optimistic
  version compare (stale and ahead writers both rejected). Rejections carry a
  fully constructed error (stable `error_code` included); **decision precedence
  is contractual: admission → version → success**. Typed identifiers throughout
  (`AbstractSet[EventId]`). `ValueError` only for internal misuse (negative
  committed version). 16 dedicated invariant tests (G1–G16). The guard decides
  and never acts — orchestration is S4.
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
