# ruflo-stratagent

**Governed management-consulting engagements for Claude Code — built on the [Ruflo](https://github.com/ruvnet/ruflo) harness.**

StratAgent takes a raw business problem (a case-interview prompt, a real client
brief, or a messy data dump) and runs a full engagement lifecycle: classify the
problem, scope it, select frameworks, dispatch specialist consultant agents,
**review and challenge** the analysis, validate it, and produce an
executive-ready report.

> This is the plugin. For the project homepage, installation, and full docs see
> the repository [root README](../../README.md) and the
> [Operations Runbook](../../docs/operations/Operations-Runbook.md).

## What it does

Run one command on any business problem:

```
/solve-case <paste the case prompt, or describe the business situation>
```

The orchestrator runs the full lifecycle (classify → gaps → plan → frame →
knowledge → analyze → **review → challenge** → validate → report → close out)
and writes all artifacts to `engagements/<slug>/`, ending with `report.md`.
**Governance is mandatory:** the Reviewer and Challenger gates run on every
engagement, and a deterministic validation gate blocks a report that isn't
evidence-traceable ([ADR-006](../../docs/architecture/ADR-006-Governance-and-Live-Validation.md)).

### Case archetypes
Profitability · market entry · pricing · cost reduction · growth · M&A ·
due diligence · new product launch · turnaround · digital transformation ·
organizational design · supply chain · customer experience · product strategy ·
and a generic diagnose-and-recommend fallback. Framework knowledge for these
lives in the governed **knowledge vault** (see below).

## What's inside

| Component | Role |
|---|---|
| `commands/solve-case.md` | The `/solve-case` entry point |
| `skills/solve-case/SKILL.md` | The engagement orchestrator (the lifecycle brain) |
| `agents/*.md` | **16 specialist subagents** (see below) |
| `knowledge/frameworks/` | **Deprecated redirect stubs** — frameworks now live in `knowledge-vault/frameworks/` (single source of truth; see `_MIGRATION.md`) |

**The 16 agents** (specs: [ADR-005](../../docs/architecture/ADR-005-Agent-Specifications.md)):
`case-classifier`, `information-gap`, `planner`, `framework-selector`,
`framework-strategist` (legacy), `issue-tree-generator`, `knowledge-agent`,
`financial-analyst`, `market-analyst`, `operations-analyst`, `strategy-analyst`,
`risk-analyst`, `reviewer`, `challenger`, `report-writer`, `knowledge-curator`.

The deterministic platform (`packages/`) provides the state aggregate, knowledge
retrieval, governance gates, the validation gate, reporting, the evidence-provider
seam, and telemetry — see the [root README](../../README.md#architecture).

## Design principles

- **Evidence over assertion.** Every number traces to a given fact or an
  explicit `[ASSUMPTION: ...]`. These labels survive into the final report.
- **One challenge pass, always.** `challenger` runs on every engagement before
  the report — not only on request (governance gates are mandatory).
- **Frameworks are tools, not scripts.** Framework selection adapts/combines
  frameworks to the actual question instead of reciting a template.

## Install

This repo is a local Ruflo marketplace. From a Claude Code terminal in the
repo root:

```
/plugin marketplace add .
/plugin install ruflo-stratagent@stratagent
```

Then `/solve-case ...` in any project.

### Standalone dev (no install)
The repo root exposes the agents and skill via `.claude/` symlinks into this
plugin, so running `claude` in the repo root picks up `/solve-case` directly
without installing. Use one mode at a time.

## Built on Ruflo

StratAgent is the **consulting vertical**; Ruflo provides the horizontal
harness. The orchestrator detects and uses these Ruflo capabilities when the
full harness is installed (`npx ruflo init`), and degrades gracefully to files
when they're absent — see "Integration with Ruflo" in
[`skills/solve-case/SKILL.md`](skills/solve-case/SKILL.md).

| StratAgent needs | Ruflo plugin it composes with |
|---|---|
| Evidence ledger + cross-engagement memory | `ruflo-rag-memory`, `ruflo-agentdb` (via `mcp__claude-flow__memory_*`) |
| Specialist swarm dispatch | `ruflo-swarm` |
| Engagement planning / replanning | `ruflo-goals` |
| Lifecycle quality gates pattern | `ruflo-sparc` |
| Cost attribution + tracing | `ruflo-cost-tracker`, `ruflo-observability` |
| PII / prompt-injection guardrails | `ruflo-aidefence` |
| Market data for entry/M&A cases | `ruflo-market-data` |

Plugin-only (no `ruflo init`): fully functional, file-based, no MCP server.

## Status

`v0.1.0-rc2` — **Ready for Limited Beta**. Decision support under mandatory human
review, not an autonomous advisor. Independent evaluation and known limitations:
[Research Evaluation](../../docs/reviews/v1.0-Research-Evaluation.md). Roadmap:
[ROADMAP.md](../../ROADMAP.md).
