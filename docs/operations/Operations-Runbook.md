# StratAgent — Operations Runbook

**Audience:** any engineer, researcher, or operator taking ownership of
StratAgent with no prior project knowledge.
**Read after:** the repo [README](../../plugins/ruflo-stratagent/README.md) and
[CLAUDE.md](../../CLAUDE.md). This runbook is the canonical operational manual.
**Version at time of writing:** `0.1.0-rc2` (RC1.2). **Maturity:** *Ready for
Limited Beta* (see [Research Evaluation](../reviews/v1.0-Research-Evaluation.md)).

This document **cross-references** the ADRs and design docs rather than
duplicating them. When a section says "see ADR-00X", that ADR is the source of
truth; this runbook tells you how to *operate*, not re-derive the design.

## Table of contents
1. [System overview](#1-system-overview)
2. [System workflow](#2-system-workflow)
3. [Deployment](#3-deployment)
4. [Operations](#4-operations)
5. [Maintenance](#5-maintenance)
6. [Failure modes](#6-failure-modes)
7. [Product evolution](#7-product-evolution)
8. [Operational checklists](#8-operational-checklists)
9. [Appendices](#9-appendices)

---

## 1. System overview

### 1.1 What StratAgent is
StratAgent is an **AI management-consulting platform**, packaged as a Claude Code
plugin built on the [Ruflo](https://github.com/ruvnet/ruflo) harness. It takes a
raw business problem (an interview-style prompt, a real client brief, or a messy
data dump) and runs a **full consulting engagement**: classify → scope → frame →
retrieve knowledge → analyze → **review → challenge** → validate → report.

### 1.2 What problems it solves
- Turns an ambiguous business question into a **structured, governed, auditable**
  consulting deliverable.
- Enforces **evidence discipline**: every number traces to a client fact or a
  labeled `[ASSUMPTION]` with a breakeven.
- Stress-tests its own conclusions (a mandatory Challenger pass) so
  recommendations arrive with their caveats and failure conditions attached.

**What it is *not*** (operator must internalize): it is *decision support*, not a
decision-maker; its numbers are assumptions unless the user supplied data (the
knowledge vault ships **no benchmarks** by design — ADR-003 D-6); and it is
**non-deterministic** (same prompt can differ across runs). See
[§7.1 Current limitations](#71-current-limitations).

### 1.3 High-level architecture
StratAgent is the **consulting vertical**; Ruflo is the **horizontal harness**
(orchestration, memory, MCP, cost/observability, guardrails). The system has two
cooperating layers:

```
┌─────────────────────────────────────────────────────────────────────┐
│  LLM layer (prompts)                                                  │
│   commands/solve-case.md → skills/solve-case/SKILL.md (orchestrator)  │
│   16 specialist subagents (agents/*.md) — classify … report           │
└───────────────┬─────────────────────────────────────────────────────┘
                │ dispatches / reads-writes engagement artifacts
┌───────────────▼─────────────────────────────────────────────────────┐
│  Python platform (packages/, deterministic libraries)                │
│   state · persistence · replay   (frozen core aggregate + event log)  │
│   knowledge (vault retrieval) · planning · analysis · governance      │
│   reporting (render + validate) · orchestration (live gate)           │
│   evidence (provider seam) · telemetry (observability)                │
└─────────────────────────────────────────────────────────────────────┘
```

Authoritative design: [ADR-001 System Architecture](../architecture/ADR-001-System-Architecture.md),
[Architecture-v1.0](../reviews/Architecture-v1.0.md),
[Execution-Flow](../architecture/Execution-Flow.md).

### 1.4 Major subsystems
| Subsystem | Package(s) | Role | Reference |
|---|---|---|---|
| Engagement State | `state`, `persistence`, `replay` | Root aggregate, append-only event log, replay engine. **Frozen — do not modify.** | ADR-002 |
| Knowledge | `knowledge` + `knowledge-vault/` | Framework/domain notes + retrieval adapter | ADR-003, ADR-004 |
| Planning | `planning` | MECE issue-tree validator, planning preconditions | ADR-005 |
| Analysis | `analysis` | Analysis-block contracts | ADR-005 |
| Governance | `governance` | Lifecycle transitions + Reviewer/Challenger gates | ADR-002, ADR-006 |
| Reporting | `reporting` | `render_report` + structural validation | — |
| Orchestration bridge | `orchestration` | Live validation gate + telemetry bridge | ADR-006 |
| Evidence providers | `evidence` | Pluggable sourced-evidence seam (no providers shipped) | ADR-007 |
| Telemetry | `telemetry` | Operational observability (spans, analytics) | [observability/](../observability/Telemetry-Architecture.md) |
| Foundation | `common`, `core` | Errors, config, logging, base models | — |

### 1.5 Design philosophy & engineering principles
From [CLAUDE.md](../../CLAUDE.md):
- **Evidence over assertion.** Every number → a given fact or a labeled
  `[ASSUMPTION]`; labels survive into the final report.
- **One challenge pass, always.** The Challenger runs on *every* engagement
  before the report (ADR-006 makes both governance gates mandatory).
- **Frameworks are tools, not scripts.** Adapt/combine frameworks to the actual
  case, don't force a template.

Engineering principles (how the code is built):
- **Immutability** — `state` is frozen Pydantic v2; value objects are frozen
  dataclasses; mutate via `model_copy(update={...})`.
- **Determinism where it's code** — validators, gates, renderer, analytics are
  pure/deterministic; only the LLM layer is non-deterministic.
- **Additive layering** — `evidence`, `orchestration`, `telemetry` are additive;
  `state/persistence/replay` and the ADRs are treated as frozen.
- **Strict quality bar** — `ruff` (E,F,I,UP,B,SIM) + `black` + `mypy --strict` +
  `pytest`; `pythonpath=["packages"]`, import as top-level names.

---

## 2. System workflow

### 2.1 Complete engagement lifecycle
The lifecycle state machine (ADR-002 §Lifecycle; enforced by
`governance/transitions.py`) has 13 forward states plus terminal `FAILED`/
`ABORTED`:

```
INTAKE → CLASSIFYING → GAP_ANALYSIS → PLANNING → FRAMING → ISSUE_TREE →
KNOWLEDGE → ANALYSIS → EVIDENCE_VALIDATION → REVIEW → CHALLENGE →
REPORTING → COMPLETED
   REVIEW → ANALYSIS (rework)   CHALLENGE → REVIEW/ANALYSIS (rework)
   any non-terminal → FAILED | ABORTED
```

### 2.2 Agent sequence & full data flow
Driven by [skills/solve-case/SKILL.md](../../plugins/ruflo-stratagent/skills/solve-case/SKILL.md).
Canonical execution flow (also in [Execution-Flow.md](../architecture/Execution-Flow.md)):

```
/solve-case <problem>
  Phase 0  setup            frameworks ← knowledge-vault/frameworks/ (single source, RC1.2)
  Phase 1  case-classifier          → 01-intake.md
  Phase 1b information-gap           → 01b-gaps.md   (seed load-bearing assumptions)
  Phase 2  planner                  → 02-plan.md
  Phase 3  framework-selector ∥ issue-tree-generator (MECE-validated)
  Phase 4  knowledge-agent          → retrieve() over the vault
  Phase 5  analysts (financial / market / operations / strategy / risk)
  Phase 6  REVIEWER  ── mandatory ── verdict approved|needs_rework  (rework loop ≤2)
  Phase 7  CHALLENGER ─ mandatory ── verdict stands|stands_with_caveats|needs_rework
  Phase 8a LIVE VALIDATION GATE  → scripts/validate_engagement.py (BLOCKS on fail)
  Phase 8b report-writer            → engagements/<slug>/report.md
  Phase 9  knowledge-curator (optional vault write-back)
  Phase 10 close out + telemetry summary
```

The 16 agents and their state ownership are specified in
[ADR-005](../architecture/ADR-005-Agent-Specifications.md); see the
[Agent map](#92-agent-map).

### 2.3 Knowledge retrieval
`knowledge.retrieve(query, vault_dir="knowledge-vault")` scans the **single
authoritative** framework/knowledge store (`knowledge-vault/`, RC1.2 unified it;
the plugin's old `knowledge/frameworks/*.md` are deprecated redirect stubs — see
`knowledge/frameworks/_MIGRATION.md`). Retrieval ranks notes by frontmatter
(`domains`/`tags`/`when_to_use`) and evidence-pins results to the git commit.
Design: ADR-003, ADR-004, [knowledge-layer.md](../architecture/knowledge-layer.md).

### 2.4 Governance
Two mandatory gates (ADR-006): **Reviewer** (5 checks — MECE, evidence,
consistency, calibration, gap-closure → `approved`/`needs_rework`) and
**Challenger** (6 stress tests → `stands`/`stands_with_caveats`/`needs_rework`).
On `needs_rework` the orchestrator re-dispatches the implicated analyst(s) and
re-runs the gate (≤2 cycles). Enforced in `governance/gates.py`.

### 2.5 Validation
Before any report is delivered, the orchestrator serializes the engagement to
`engagements/<slug>/state.json` and runs the **deterministic report gate**
(`orchestration/report_gate.py` → `enforce_render_ready` + `validate_consistency`).
Failure **blocks** report generation with actionable diagnostics. See ADR-006 and
[§4.4](#44-validation).

### 2.6 Reporting
`reporting.render_report(state)` is a pure function → deterministic Markdown. In
the **live** path the LLM `report-writer` authors the narrative report; the
deterministic renderer is used for validation/tests. Every `[ASSUMPTION]` label
and both governance verdicts survive into the report.

### 2.7 Telemetry
Operational observability (`telemetry` package) records a span per agent
dispatch (durations, tokens, retries, verdicts) to `telemetry/<engagement_id>.jsonl`,
**separate** from the ADR-002 domain event log, correlated by `engagement_id`.
Analytics derive reviewer pass rate, challenger intervention, rework frequency,
per-phase durations, etc. Design + samples:
[observability/](../observability/Telemetry-Architecture.md),
[Telemetry-Integration-Report](../observability/Telemetry-Integration-Report.md).

### 2.8 Replay
Two distinct "replay" concepts — do not confuse them:
- **State replay** (`packages/replay`, ADR-002) — reconstructs an
  `EngagementState` from its append-only domain event log. Core, frozen.
- **Telemetry replay** (`scripts/replay_pilots.py`) — rebuilds the three pilot
  telemetry traces from observed run logs into `docs/observability/samples/`.

---

## 3. Deployment

> There is **no server**. StratAgent runs inside Claude Code (as a plugin or
> standalone) plus a `uv`-managed Python environment for the deterministic layer.

### 3.1 Dependencies
- **Python ≥ 3.12** and **[uv](https://docs.astral.sh/uv/)** (package/venv manager).
- **Claude Code** (CLI/desktop/IDE) to run the `/solve-case` skill and subagents.
- Runtime Python deps (from `pyproject.toml`): `pydantic>=2.7`,
  `pydantic-settings>=2.3`, `pyyaml>=6.0.3`. Dev deps: `ruff`, `black`, `mypy`,
  `pytest`, `pytest-cov`, `pytest-benchmark`, `pre-commit`, `types-pyyaml`.
- **Optional:** the full Ruflo harness (`npx ruflo init`) registers
  `mcp__claude-flow__*` tools (vector memory, swarm, cost/observability). The
  orchestrator auto-detects and degrades to plain files if absent.

### 3.2 Installation
```bash
# 1. clone, then from the repo root:
uv sync                      # create venv + install deps (or `uv run <cmd>` lazily)

# 2a. Standalone dev (no plugin install): run claude in the repo root.
#     .claude/agents, .claude/skills, reference/frameworks are symlinks into the
#     plugin, so /solve-case works directly.

# 2b. As an installed plugin (from a Claude Code terminal in repo root):
/plugin marketplace add .
/plugin install ruflo-stratagent@stratagent
```

### 3.3 Configuration & environment variables
Configuration is centralized in `packages/core/config.py` (`get_settings()`,
pydantic-settings) and `packages/core/logging.py`. Settings are read from the
environment; `log_level` controls verbosity. **Do not scatter config** — add new
settings behind `get_settings()`. There are **no secrets required** for the core
system (no external API keys; the vault has no live data sources). If/when an
Evidence Provider (ADR-007) is attached, its credentials are the provider's
concern, injected at registration — never committed.

### 3.4 Repository layout
```
.claude-plugin/marketplace.json     marketplace manifest
plugins/ruflo-stratagent/           THE PLUGIN (source of truth)
  commands/solve-case.md            /solve-case entry point
  skills/solve-case/SKILL.md        engagement orchestrator (lifecycle brain)
  agents/*.md                       16 specialist subagents
  knowledge/frameworks/*.md         deprecated redirect stubs (+ _MIGRATION.md)
  README.md                         full plugin docs
packages/                           13 Python packages (deterministic layer)
scripts/                            CLI tools (validate, telemetry, schema)
tests/                              pytest suite (954 tests), mirrors packages/
knowledge-vault/                    THE knowledge source of truth (read-only notes)
engagements/                        per-engagement output artifacts (runtime)
telemetry/                          per-engagement JSONL traces (runtime)
docs/                               architecture, guides, observability, beta, reviews, operations
.claude/*, reference/frameworks     symlinks into the plugin (standalone dev)
```
See also [DEVELOPER_GUIDE](../guides/DEVELOPER_GUIDE.md) for the package contract.

### 3.5 Startup sequence
There is no long-running process. "Startup" = environment readiness:
1. `uv sync` (once).
2. Confirm the toolchain (see [§3.6 Verification](#36-verification)).
3. Start Claude Code in the repo root (or install the plugin).
4. Run `/solve-case <problem>`.

### 3.6 Verification (do this after install / after any change)
```bash
uv run ruff check packages tests scripts     # lint            → "All checks passed!"
uv run black --check packages tests scripts   # format          → all files unchanged
uv run mypy                                    # types (strict)  → Success, 90 files
uv run pytest -q                               # tests           → 954 passed
uv run python scripts/replay_pilots.py         # telemetry smoke → writes 3 sample traces
```
All green ⇒ the deterministic layer is healthy. The LLM layer is verified by
running an actual `/solve-case` engagement (see [§4.1](#41-running-engagements)).

---

## 4. Operations

### 4.1 Running engagements
```
/solve-case <paste the case prompt or describe the business problem>
```
Outputs land in `engagements/<slug>/` (intake, gaps, plan, framework, issue-tree,
knowledge, analyst blocks, review, challenge, `state.json`, `report.md`). Expect
a run to take **minutes to tens of minutes** — it is model-inference-bound, ~11–13
subagent dispatches. Supply real numbers in the prompt where you have them; the
system labels everything else `[ASSUMPTION]`.

### 4.2 Running benchmarks / evaluation
- **Consulting-quality benchmark:** the 30-case dataset + 14-criterion rubric in
  [v1.0-Validation-Benchmark](../reviews/v1.0-Validation-Benchmark.md); method +
  results in [v1.0-Research-Evaluation](../reviews/v1.0-Research-Evaluation.md).
  New engagements are genuine LLM runs (expensive, non-deterministic); do not
  fabricate scores.
- **Deterministic perf baselines:** `uv run pytest tests/perf` (pytest-benchmark).
- **Telemetry pilot replay:** `uv run python scripts/replay_pilots.py`.

### 4.3 Telemetry
```bash
# one engagement's operational analytics (durations, confidence, frameworks)
uv run python scripts/engagement_telemetry.py --engagement <engagement_id>
# quality metrics across all engagements (reviewer pass, challenger intervention…)
uv run python scripts/engagement_telemetry.py --all --quality
# OpenTelemetry-compatible spans
uv run python scripts/engagement_telemetry.py --engagement <engagement_id> --otlp
# append one span (used by the orchestrator via Bash; also for manual backfill)
uv run python scripts/record_telemetry.py --engagement <id> --agent <name> \
  --phase <phase> --status finished --duration-ms <ms> [--meta verdict=approved]
```
Reference: [observability/API-Contracts](../observability/API-Contracts.md),
[observability/samples/](../observability/samples/README.md).

### 4.4 Validation
```bash
# gate an engagement before its report is delivered (exit 0 = ok, 1 = blocked)
uv run python scripts/validate_engagement.py <slug-or-path-to-state.json>
```
On failure it prints `(check:rule) [section] detail` diagnostics naming the
responsible section. **No report may bypass this gate** (ADR-006).

### 4.5 State replay (recovery / audit)
Use `packages/replay` to reconstruct an `EngagementState` from its domain event
log (ADR-002, [replay-layer.md](../architecture/replay-layer.md)). This is how
you audit *what happened* to an engagement and recover state.

### 4.6 Logs & expected outputs
- **Structured logs:** via `core/logging.py` (`get_logger`); `log_level` env var.
  Prefer structured over free-form (telemetry is the structured operational feed).
- **Telemetry:** `telemetry/<engagement_id>.jsonl` (one JSON event per line).
- **Engagement artifacts:** `engagements/<slug>/*.md` + `state.json` + `report.md`.
- **Expected report shape:** exec summary → situation → framework → analysis →
  recommendation → risks/what-would-change → appendices (assumptions, evidence,
  confidence). Both governance verdicts appear; every `[ASSUMPTION]` is labeled.

### 4.7 Troubleshooting (quick index → §6 for depth)
| Symptom | First check |
|---|---|
| `ModuleNotFoundError` running a script | run via `uv run`; scripts bootstrap `packages/` onto `sys.path` |
| Report gate blocks | read the diagnostics; route the named issue to the owning agent (§6.4) |
| Challenger returns `needs_rework` | expected governance — fix the analysis, re-run (§6.5) |
| `retrieve()` returns nothing | check `vault_dir` and note frontmatter (§6.6) |
| Timing test flaky | `test_retrieve_multiple_queries_consistent` is timing-sensitive under coverage (§6.1) |

---

## 5. Maintenance

### 5.1 Updating the knowledge vault
- The vault (`knowledge-vault/`) is the **single source of truth** for frameworks
  and domain knowledge (RC1.2). Notes are treated as **read-only content** —
  human-curated; only the `knowledge-curator` agent writes `status: draft` notes.
- Every note carries ADR-003 frontmatter (`id`, `type`, `title`, `domains`,
  `when_to_use`, `visibility`, `last_verified`, `status`). Validate changes with
  `uv run pytest tests/knowledge`.
- **Do not** re-introduce a second framework store. The plugin cheat sheets are
  deprecated stubs; keep the vault canonical (ADR-006 convergence, `_MIGRATION.md`).

### 5.2 Adding frameworks
Add a new note under `knowledge-vault/frameworks/<id>.md` with correct frontmatter
(copy an existing note's header). No code change needed — retrieval discovers it
by frontmatter. Optionally add it to the archetype hint index in
`plugins/ruflo-stratagent/knowledge/frameworks/_MIGRATION.md`.

### 5.3 Adding analysts (agents)
1. Add `plugins/ruflo-stratagent/agents/<name>.md` with an ADR-005-style contract
   (single responsibility, owner-exclusive state writes, pre/postconditions).
2. Wire it into `skills/solve-case/SKILL.md` at the right phase.
3. If it writes an analysis block, ensure `analysis/contracts.py` covers it.
4. Add telemetry recording for it in the SKILL (span per dispatch).
5. **Never** put private memory in an agent or let it write another agent's state
   (ADR-005). Update the [Agent map](#92-agent-map).

### 5.4 Updating ADRs
ADR-001…005 are `status: Proposed`; ADR-006/007 are `Accepted`. **Do not rewrite
an accepted ADR** — supersede it with a new one (`supersedes:` header), as ADR-006
did for the lightweight-skip rule. Record decisions, don't silently drift.

### 5.5 Regression testing
```bash
uv run pytest -q            # full suite (954)
uv run pytest tests/<area>  # scoped (state, governance, reporting, telemetry, …)
uv run pytest --cov=packages --cov-report=term-missing   # coverage
```
The convergence guards in `tests/convergence/` pin architectural invariants
(single framework store, mandatory gates) — treat a failure there as
architecture drift, not a flaky test.

### 5.6 Versioning
- Version lives in `pyproject.toml` (`0.1.0-rc2`). Use **valid PEP 440**
  (`0.1.0-rc2`, not `0.1.0-rc1.2` — the latter breaks `uv`).
- Telemetry has its own `TELEMETRY_SCHEMA_VERSION` (additive changes don't bump).
- `CHANGELOG.md` groups changes under `[Unreleased]` per sprint until a tagged
  release.

### 5.7 Release process
1. Land changes on a branch; ensure the full [§3.6 verification](#36-verification)
   is green.
2. Update `CHANGELOG.md` and (if bumping) `pyproject.toml` version.
3. Run the [Release checklist](#82-release-checklist) and the GA gate in
   [beta/Release-Checklist](../beta/Release-Checklist.md) +
   [beta/Go-No-Go-Framework](../beta/Go-No-Go-Framework.md).
4. Tag; write release notes (pattern: `docs/reviews/RC*-Release-Notes.md`).

---

## 6. Failure modes

### 6.1 Common failures & recovery
| Failure | Cause | Recovery |
|---|---|---|
| `ModuleNotFoundError: telemetry/state/...` in a script | ran bare `python` | use `uv run python …`; scripts insert `packages/` on `sys.path` |
| Flaky `test_retrieve_multiple_queries_consistent` | 200 ms wall under coverage | re-run in isolation; known timing sensitivity (RC1 audit T-2) |
| `uv` refuses the project | invalid version string | fix `pyproject.toml` version to valid PEP 440 |
| Subagent `Write` blocked | harness sandbox | orchestrator persists the artifact instead (known execution nuance) |

### 6.2 Telemetry diagnosis
When an engagement behaves oddly, read its trace:
```bash
uv run python scripts/engagement_telemetry.py --engagement <id>
```
Look for: a `failed` span (which phase broke), an outlier `duration_by_phase_ms`
(e.g. a multi-minute analyst — the risk-analyst is a known slow-span class),
`rework_count > 0` (a governance loop fired), or `validation_failures > 0`. For a
fleet view use `--all --quality` (reviewer pass rate, challenger intervention,
needs-rework frequency). Dashboards: [observability/Dashboards](../observability/Dashboards.md).

### 6.3 Validation failures (report gate)
Symptom: `scripts/validate_engagement.py` exits 1 / "report gate BLOCKED".
Diagnose from the printed rule:
- `REVIEWER_GATE_NOT_RUN|NOT_APPROVED` → the Reviewer didn't run/approve; run it.
- `CHALLENGER_GATE_NOT_RUN|NOT_CLEARED` → run the Challenger / it returned rework.
- `UNEVIDENCED_FINDING` → an answered finding cites no evidence/assumption — send
  it back to the owning analyst.
- `ASSUMPTION_NO_BREAKEVEN` → a load-bearing assumption lacks a breakeven.
- `INCOMPLETE_ANALYSIS_BLOCK` → a COMPLETE block has an unanswered finding.
Fix at the source in `state.json`, re-run the gate. Never edit around it.

### 6.4 Governance failures
- **Reviewer `needs_rework`:** re-dispatch the implicated analyst(s) with the
  reviewer's issues; re-run Reviewer (≤2 cycles, then escalate to a human).
- **Challenger `needs_rework`:** this is the system working (it caught an
  overconfident or inconsistent conclusion — e.g. the Halberd $343M reconciliation
  in the pilots). Fix the analysis; re-run Reviewer→Challenger.
- **Do not** bypass a gate or lower a verdict to ship — it defeats the platform's
  core value (governance is its measured differentiator vs. a single-pass model).

### 6.5 Knowledge failures
- `retrieve()` returns `[]`: confirm `vault_dir` points at `knowledge-vault/`,
  the note has valid frontmatter, and the query terms match `domains`/`when_to_use`.
- "No benchmark numbers": **expected** — the vault holds frameworks, not data
  (ADR-003 D-6). Numbers become `[ASSUMPTION]`s. To supply real data, attach an
  Evidence Provider (ADR-007) or put facts in the prompt.
- Frontmatter validation errors: `uv run pytest tests/knowledge`.

### 6.6 When to use state replay
- To **audit** an engagement: replay its domain event log to see every state
  transition (ADR-002).
- To **recover** after an interruption: reconstruct `EngagementState` from the log
  rather than trusting a partial in-memory copy.
- Not for debugging *quality* — use telemetry + the engagement artifacts for that.

---

## 7. Product evolution

### 7.1 Current limitations
From the [Research Evaluation](../reviews/v1.0-Research-Evaluation.md) (verdict
*Ready for Limited Beta*, mean 7.6/10, n=3, 0 hallucinations):
1. **Empty evidence base** — every quantitative claim is a labeled assumption
   unless the user supplied data. The single biggest gap for production.
2. **Non-determinism** — same input can yield different recommendations.
3. **LLM latency/cost** — engagements take minutes; ~11–13 dispatches each.
4. **Small validation sample** — quality is proven on 3 genuine engagements.

### 7.2 Technical debt (tracked)
- RC1 audit backlog: leaf-detection duplicated across `preconditions.py`/`gates.py`;
  a couple of unreachable defensive branches. See
  [RC1-Engineering-Audit](../reviews/RC1-Engineering-Audit.md).
- ADR-001…005 remain `status: Proposed` (not ratified).
- Live per-agent telemetry spans are **instruction-driven** (SKILL), not
  code-enforced ([Telemetry-Integration-Report §7](../observability/Telemetry-Integration-Report.md)).
- `CLAUDE.md`'s "Framework library" line still describes the pre-RC1.2 model.

### 7.3 Roadmap
- **Evidence-provider rollout (ADR-007):** implement one concrete provider
  (market data / benchmarks), register it, and promote `ProviderResult`s into the
  Evidence Ledger as `external_source` records. Closes limitation §7.1(1).
- **Future telemetry:** Phase 4 in
  [observability/Implementation-Plan](../observability/Implementation-Plan.md) —
  an OTLP exporter `Sink`, dashboard stand-up, aggregate-then-prune retention job.
- **Enterprise deployment:** multi-tenant isolation is scoped by `engagement_id`
  upstream; before enterprise use, run the [beta program](../beta/Beta-Program-Guide.md),
  add auth/privacy review, and populate an evidence provider.
- **Larger evaluation:** n≥12 genuine engagements + a non-Claude judge to remove
  the shared-model threat.

### 7.4 Human review (non-negotiable)
StratAgent output is decision *support*. A qualified human must verify **every
number** against real data, confirm the load-bearing assumptions and breakevens,
and own the final recommendation before it is used or shared. Prohibited uses
(regulated finance/legal/medical, live trading, irreversible high-stakes without
expert review) are listed in [beta/Beta-Program-Guide §5](../beta/Beta-Program-Guide.md#5-ethics--appropriate-use-full).

---

## 8. Operational checklists

### 8.1 Daily checklist (operator)
- [ ] Toolchain green: `ruff` / `black --check` / `mypy` / `pytest -q`.
- [ ] Spot-check recent engagements: any `failed` spans?
      `scripts/engagement_telemetry.py --all --quality`.
- [ ] Reviewer pass rate and challenger intervention within expected bands (not
      100% rubber-stamp, not collapsing).
- [ ] No report shipped with an un-cleared gate (spot-check `state.json` verdicts).
- [ ] Disk: prune old `telemetry/*.jsonl` per retention policy
      ([observability/Retention-Privacy](../observability/Retention-Privacy.md)).

### 8.2 Release checklist
- [ ] Full verification green (§3.6). [ ] `CHANGELOG.md` updated.
- [ ] Version valid PEP 440. [ ] Convergence guards pass (`tests/convergence`).
- [ ] GA blockers closed ([beta/Release-Checklist](../beta/Release-Checklist.md)).
- [ ] Go/No-Go returns GO ([beta/Go-No-Go-Framework](../beta/Go-No-Go-Framework.md)).
- [ ] Release notes written. [ ] Tag created.

### 8.3 Incident checklist
- [ ] Identify the engagement(s) and pull the telemetry trace (§6.2).
- [ ] Classify: validation / governance / knowledge / infra (§6).
- [ ] Contain: block the affected report path; do not ship un-gated output.
- [ ] Root-cause from the trace + engagement artifacts + (if needed) state replay.
- [ ] Fix at source; add a regression test; re-run the gate.
- [ ] If a hallucination is confirmed → **release blocker** until fixed (§8.2).

### 8.4 Beta checklist
Follow [beta/Participant-Instructions](../beta/Participant-Instructions.md) and
[beta/Success-Metrics](../beta/Success-Metrics.md): recruit data-capable
participants, assign guided + BYO cases spanning ambiguity tiers, collect
post-engagement forms, enforce human review of every number, track the 10 metrics,
respect the small-n rule.

### 8.5 Evaluation checklist
- [ ] Use the benchmark + rubric ([v1.0-Validation-Benchmark](../reviews/v1.0-Validation-Benchmark.md)).
- [ ] Run **genuine** engagements; never fabricate runs/scores/CIs.
- [ ] Separate execution from scoring; score adversarially.
- [ ] Report distributions + threats to validity; state n honestly.
- [ ] Baseline against a single-pass model to show marginal value.

---

## 9. Appendices

### 9.1 Glossary
| Term | Meaning |
|---|---|
| Engagement | One end-to-end run of `/solve-case` on a business problem |
| EngagementState | The root aggregate holding all engagement data (ADR-002); frozen |
| Domain event | An ADR-002 business fact (e.g. `ReviewerApproved`), append-only log |
| Telemetry event | An *operational* observability span (duration/tokens/status); separate |
| Issue tree | MECE decomposition of the real question into owned, testable sub-questions |
| Load-bearing assumption | An assumption that, if wrong, flips the recommendation; carries a breakeven |
| Breakeven | The threshold at which a recommendation inverts |
| Governance gate | Reviewer (analysis) / Challenger (recommendation); both mandatory (ADR-006) |
| Report gate | Deterministic validation before report delivery (`orchestration/report_gate.py`) |
| Archetype | Case type (profitability, market entry, M&A, …) driving framework selection |
| Evidence Provider | Pluggable sourced-evidence seam (ADR-007); none shipped |
| Verdict | Reviewer: approved/needs_rework · Challenger: stands/stands_with_caveats/needs_rework |

### 9.2 Package map
`common` (errors) · `core` (config, logging) · `state` (+`persistence`, `replay`)
*frozen core* · `knowledge` (vault retrieval) · `planning` (MECE, preconditions) ·
`analysis` (block contracts) · `governance` (transitions, gates) · `reporting`
(render + validate) · `orchestration` (live gate + telemetry bridge) · `evidence`
(provider seam) · `telemetry` (observability). Contract details:
[DEVELOPER_GUIDE](../guides/DEVELOPER_GUIDE.md).

### 9.3 Agent map (16, ADR-005)
Intake: `case-classifier`, `information-gap` · Plan/frame: `planner`,
`framework-selector`, `framework-strategist` (legacy), `issue-tree-generator` ·
Knowledge: `knowledge-agent` · Analysts: `financial-analyst`, `market-analyst`,
`operations-analyst`, `strategy-analyst`, `risk-analyst` · Governance: `reviewer`,
`challenger` · Output: `report-writer` · Write-back: `knowledge-curator`.
Specs + state ownership: [ADR-005](../architecture/ADR-005-Agent-Specifications.md).

### 9.4 ADR index
| ADR | Title | Status |
|---|---|---|
| [001](../architecture/ADR-001-System-Architecture.md) | System Architecture | Proposed |
| [002](../architecture/ADR-002-Engagement-State.md) | Engagement State | Proposed |
| [003](../architecture/ADR-003-Knowledge-Architecture.md) | Knowledge Architecture | Proposed |
| [004](../architecture/ADR-004-Consulting-Knowledge-Library.md) | Consulting Knowledge Library | Proposed |
| [005](../architecture/ADR-005-Agent-Specifications.md) | Agent Specifications | Proposed |
| [006](../architecture/ADR-006-Governance-and-Live-Validation.md) | Governance & Live Validation | **Accepted** |
| [007](../architecture/ADR-007-Evidence-Providers.md) | Evidence Providers | **Accepted** |
Supporting: [Execution-Flow](../architecture/Execution-Flow.md),
[Event-Design-Principles](../architecture/Event-Design-Principles.md),
[knowledge-layer](../architecture/knowledge-layer.md),
[replay-layer](../architecture/replay-layer.md),
[projection-versioning](../architecture/projection-versioning.md).

### 9.5 Command reference
```bash
# Quality gate
uv run ruff check packages tests scripts
uv run black --check packages tests scripts
uv run mypy
uv run pytest -q
uv run pytest --cov=packages --cov-report=term-missing

# Engagement
/solve-case <problem>                                   # (in Claude Code)
uv run python scripts/validate_engagement.py <slug>     # live validation gate

# Telemetry
uv run python scripts/engagement_telemetry.py --engagement <id>
uv run python scripts/engagement_telemetry.py --all --quality
uv run python scripts/engagement_telemetry.py --engagement <id> --otlp
uv run python scripts/record_telemetry.py --engagement <id> --agent <n> --phase <p> --status finished
uv run python scripts/replay_pilots.py

# Schema / traceability
uv run python scripts/generate_schema.py
uv run python scripts/generate_traceability.py
```

### 9.6 Useful scripts (`scripts/`)
| Script | Purpose |
|---|---|
| `validate_engagement.py` | Run the deterministic report gate on an engagement (blocking) |
| `record_telemetry.py` | Append one telemetry span (orchestrator Bash bridge / backfill) |
| `engagement_telemetry.py` | Summarize/export telemetry (analytics JSON, OTLP) |
| `replay_pilots.py` | Rebuild the 3 pilot telemetry traces + verify analytics |
| `generate_schema.py` | Emit the `EngagementState` JSON schema |
| `generate_traceability.py` | Generate the ADR-002 traceability matrix |

### 9.7 Key documents to read next
[README](../../plugins/ruflo-stratagent/README.md) → [CLAUDE.md](../../CLAUDE.md) →
[QUICKSTART](../guides/QUICKSTART.md) → [USER_GUIDE](../guides/USER_GUIDE.md) →
[DEVELOPER_GUIDE](../guides/DEVELOPER_GUIDE.md) → ADR-001/002/005/006/007 →
[Execution-Flow](../architecture/Execution-Flow.md) →
[observability/](../observability/Telemetry-Architecture.md).

---

*This runbook is documentation only — no source code, prompts, or architecture
were changed in producing it. Keep it current: when you land a change that alters
a command, path, package, agent, or failure mode, update the relevant section here
in the same PR.*
