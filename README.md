<div align="center">

# StratAgent

**An AI management-consulting platform — packaged as a Claude Code plugin, built on the [Ruflo](https://github.com/ruvnet/ruflo) harness.**

Give it a business problem. It runs a full, *governed* consulting engagement —
classify → scope → frame → analyze → **review → challenge** → validate → report —
and hands back an executive-ready deliverable where every number traces to a fact
or a labeled assumption.

`v0.1.0-rc2` · Python ≥ 3.12 · MIT License · **Maturity: Ready for Limited Beta**

</div>

---

> [!IMPORTANT]
> **StratAgent is decision *support*, not a decision-maker.** The knowledge vault
> ships **no benchmark data** by design, so any number is a labeled `[ASSUMPTION]`
> unless *you* supplied it. A qualified human must verify every number and own the
> final recommendation. See [Appropriate Use](docs/beta/Beta-Program-Guide.md#5-ethics--appropriate-use-full).

## What is StratAgent

StratAgent takes a raw business problem (a case-interview prompt, a real client
brief, or a messy data dump) and runs a complete consulting engagement end to
end. Its distinguishing feature is **governance**: a mandatory Reviewer gate and
a mandatory Challenger gate stress-test the analysis before any report is
produced, and a deterministic validation gate blocks a report that isn't
evidence-traceable. In independent evaluation this governance layer measurably
caught overconfidence and blind spots that a single-pass model shipped
([Research Evaluation](docs/reviews/v1.0-Research-Evaluation.md)).

## Architecture

StratAgent is the **consulting vertical**; Ruflo is the **horizontal harness**.
Two cooperating layers:

```
┌──────────────────────────────────────────────────────────────────────┐
│  LLM layer (prompts)                                                   │
│    /solve-case  →  skills/solve-case/SKILL.md   (engagement orchestrator)│
│    16 specialist subagents (agents/*.md)  —  classify … review … report │
└────────────────┬───────────────────────────────────────────────────────┘
                 │  dispatches subagents · reads/writes engagement artifacts
┌────────────────▼───────────────────────────────────────────────────────┐
│  Python platform (packages/, deterministic libraries)                   │
│    state · persistence · replay        frozen core aggregate + event log │
│    knowledge (vault retrieval) · planning · analysis · governance        │
│    reporting (render + validate) · orchestration (live validation gate)  │
│    evidence (provider seam) · telemetry (observability)                  │
└──────────────────────────────────────────────────────────────────────┘
```

Design authority: [ADR-001](docs/architecture/ADR-001-System-Architecture.md) ·
[Execution Flow](docs/architecture/Execution-Flow.md) ·
[Operations Runbook](docs/operations/Operations-Runbook.md).

## Agent workflow

```
/solve-case <problem>
  1  case-classifier ─────────── name the archetype, extract facts, list unknowns
  1b information-gap ─────────── surface load-bearing gaps → seed assumptions
  2  planner ─────────────────── ordered, dependency-aware execution plan
  3  framework-selector ∥ issue-tree-generator  (MECE-validated)
  4  knowledge-agent ─────────── retrieve framework/domain notes from the vault
  5  analysts ────────────────── financial · market · operations · strategy · risk
  6  reviewer  ⟵ MANDATORY ───── MECE, evidence, consistency, calibration, gaps
  7  challenger ⟵ MANDATORY ──── attack assumptions, counter-case, what-would-change
  8  live validation gate ────── deterministic; blocks an un-evidenced report
     report-writer ───────────── executive deliverable → engagements/<slug>/report.md
  9  knowledge-curator ───────── (optional) durable insights back to the vault
```

Governance gates are mandatory in every mode
([ADR-006](docs/architecture/ADR-006-Governance-and-Live-Validation.md)); agent
contracts are in [ADR-005](docs/architecture/ADR-005-Agent-Specifications.md).

## Features

- **Full engagement lifecycle** — 13-state machine, 16 specialist agents, one command.
- **Governance by construction** — mandatory Reviewer + Challenger + a rework loop.
- **Evidence discipline** — every number is a client fact or a labeled `[ASSUMPTION]`
  with a breakeven; labels survive into the report.
- **Deterministic validation gate** — no report ships unless it is evidence-traceable.
- **Unified knowledge vault** — one governed framework/domain store (60+ notes).
- **Evidence-provider seam** — pluggable sourced-evidence interface ([ADR-007]);
  none shipped (the platform never invents data).
- **Operational telemetry** — per-engagement JSONL traces, analytics, OTel-ready
  spans, kept separate from the domain event log.
- **Deterministic Python core** — frozen state, append-only event log, replay engine.
- **Quality bar** — `ruff` + `black` + `mypy --strict`, enforced in CI across both
  the reference core (**954 tests**) and the shipping web dashboard (**61 tests**,
  run in mock mode). See [ADR-008](docs/architecture/ADR-008-Repository-Topology.md)
  for how the three artifacts relate.

[ADR-007]: docs/architecture/ADR-007-Evidence-Providers.md

## Installation

Requires **Python ≥ 3.12**, **[uv](https://docs.astral.sh/uv/)**, and **Claude Code**.

```bash
uv sync          # install the Python platform (or `uv run <cmd>` lazily)
```

Then use it in Claude Code either **standalone** (run `claude` in the repo root —
`.claude/` symlinks expose `/solve-case`) or **as a plugin**:

```
/plugin marketplace add .
/plugin install ruflo-stratagent@stratagent
```

## Quickstart

```
/solve-case Our operating profit fell 18 points in a year — revenue is down and
costs are up. Why, and what's the fastest path to margin recovery?
```

Artifacts land in `engagements/<slug>/` (intake, plan, issue tree, analyses,
review, challenge, `state.json`, and `report.md`). Full guide:
[QUICKSTART](docs/guides/QUICKSTART.md) · [USER_GUIDE](docs/guides/USER_GUIDE.md).

## Example engagement

A genuinely-executed market-entry engagement (Northwind Cloud) was run during
evaluation. Engagement outputs are treated as **runtime artifacts** (the
`engagements/` directory is git-ignored, so they are reproduced when *you* run
`/solve-case`, not shipped). What ships in the repo is the committed evidence of
that run:

- Its **telemetry trace** (15 spans): [`docs/observability/samples/eng_northwind_eu.jsonl`](docs/observability/samples/README.md).
- The narrative in the [Research Evaluation](docs/reviews/v1.0-Research-Evaluation.md):
  the Challenger caught a **CLOUD Act sovereignty ceiling** the analysts missed,
  and the report honestly refused to call EU a 5-year NPV winner.

Two more pilots (`halberd-cost`, `harbor-vine-org`) plus single-pass baselines were
run the same way; their telemetry traces are in
[`docs/observability/samples/`](docs/observability/samples/README.md).

## Repository structure

```
plugins/ruflo-stratagent/   DOMAIN DEFINITION — commands, skill orchestrator, 16 agents
apps/dashboard/             SHIPPING PRODUCT — public web app (FastAPI + Next.js)
packages/                   REFERENCE CORE — 13 Python packages, frozen (954 tests)
scripts/                    CLI tools (validation, telemetry, schema)
tests/                      pytest suite for packages/ (954 tests)
knowledge-vault/            THE knowledge source of truth (governed notes)
engagements/                per-engagement artifacts + worked examples
docs/                       architecture, guides, operations, observability, beta, reviews
```

**Three artifacts, one product line.** The plugin's agents + vault are the
canonical consulting behaviour; `apps/dashboard/` is the production web app that
runs them (and reads the same `agents/*.md` at runtime); `packages/` is the
frozen, strictly-typed reference core. Which one to edit for a given change is
spelled out in
[ADR-008: Repository Topology](docs/architecture/ADR-008-Repository-Topology.md).

## Documentation index

| Area | Start here |
|---|---|
| **Operate it** | [Operations Runbook](docs/operations/Operations-Runbook.md) |
| Use it | [Quickstart](docs/guides/QUICKSTART.md) · [User Guide](docs/guides/USER_GUIDE.md) |
| Build on it | [Developer Guide](docs/guides/DEVELOPER_GUIDE.md) |
| Architecture | [ADRs 001–007](docs/architecture/) · [Execution Flow](docs/architecture/Execution-Flow.md) |
| Observability | [Telemetry](docs/observability/Telemetry-Architecture.md) · [Dashboards](docs/observability/Dashboards.md) |
| Evidence & quality | [Research Evaluation](docs/reviews/v1.0-Research-Evaluation.md) · [RC1 Audit](docs/reviews/RC1-Engineering-Audit.md) |
| Try with users | [Beta Program](docs/beta/Beta-Program-Guide.md) |
| Roadmap & release | [ROADMAP](ROADMAP.md) · [CHANGELOG](CHANGELOG.md) |

## Roadmap (short)

Populate an evidence provider (close the assumptions-only gap) · stand up
telemetry export + dashboards · larger genuine evaluation (n ≥ 12) · enterprise
hardening. Full list: [ROADMAP.md](ROADMAP.md).

## Contributing

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) and the
[Code of Conduct](CODE_OF_CONDUCT.md). The one-line quality gate is `make check`
(`ruff` + `black --check` + `mypy` + `pytest`). Never modify the frozen core
(`packages/state|persistence|replay`) or an accepted ADR — supersede instead.

## Security & support

Report vulnerabilities per [SECURITY.md](SECURITY.md). Getting-help paths are in
[SUPPORT.md](SUPPORT.md) and [FAQ.md](FAQ.md).

## License

[MIT](LICENSE) © 2026 Darpan. Built on [Ruflo](https://github.com/ruvnet/ruflo);
see [ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.md). If you use StratAgent in research,
please [cite it](CITATION.cff).
