# ruflo-stratagent

**Autonomous management-consulting engagements for Claude Code — built on the [Ruflo](https://github.com/ruvnet/ruflo) harness.**

StratAgent takes a raw business problem (a case-interview prompt, a real client
brief, or a messy data dump) and runs a full engagement lifecycle: classify the
problem, scope it, select frameworks, dispatch specialist consultant agents,
stress-test the conclusions, and produce an executive-ready report.

## What it does

Run one command on any business problem:

```
/solve-case <paste the case prompt, or describe the business situation>
```

The orchestrator runs a 6-phase engagement (classify → scope → frame → analyze →
challenge → synthesize → close out) and writes all artifacts to
`engagements/<slug>/` in your working directory, ending with `report.md`.

### Supported case archetypes
M&A / acquisition · profitability decline · revenue growth · cost reduction ·
new market entry · new product launch · pricing strategy · turnaround ·
and a generic diagnose-and-recommend fallback for anything that doesn't fit a
named archetype.

## What's inside

| Component | Role |
|---|---|
| `commands/solve-case.md` | The `/solve-case` entry point |
| `skills/solve-case/` | The engagement orchestrator (the lifecycle brain) |
| `agents/case-classifier` | Names the case type, extracts facts, lists unknowns |
| `agents/framework-strategist` | Picks/adapts frameworks, builds the MECE issue tree |
| `agents/financial-analyst` | P&L bridges, unit economics, valuation, sensitivity |
| `agents/market-analyst` | Market sizing, competitive dynamics, segments |
| `agents/operations-analyst` | Cost structure, capacity, process, supply chain |
| `agents/challenger` | Devil's advocate — stress-tests every recommendation |
| `agents/report-writer` | Synthesizes into an executive deliverable |
| `knowledge/frameworks/` | One cheat sheet per case archetype |

## Design principles

- **Evidence over assertion.** Every number traces to a given fact or an
  explicit `[ASSUMPTION: ...]`. These labels survive into the final report.
- **One challenge pass, always.** `challenger` runs on every engagement before
  the report — not only on request.
- **Frameworks are tools, not scripts.** `framework-strategist` adapts/combines
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
The repo root also exposes the agents and skill via `.claude/` symlinks into
this plugin, so running `claude` in the repo root picks up `/solve-case`
directly without installing. Use one mode at a time (don't install the plugin
*and* rely on the symlinks in the same workspace).

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

Plugin-only (no `ruflo init`): fully functional, file-based, no MCP server,
no hooks, no daemon.

## Status

`v0.1.0` — packaged from a working prototype. Not yet wired to the Ruflo MCP
server end to end (that activates after `ruflo init`); deck/spreadsheet
deliverable generation and a consulting eval harness are planned next.
