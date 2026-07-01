# StratAgent

An AI management-consulting platform, packaged as a **Claude Code plugin built
on the [Ruflo](https://github.com/ruvnet/ruflo) harness**. It takes a raw
business problem (interview-style prompt, real client brief, or messy data
dump) and runs a full engagement lifecycle: classify the problem, scope it,
select frameworks, dispatch specialist analysts, stress-test the conclusions,
and produce an executive-ready report.

## Repo layout

This repo is a **local Ruflo marketplace** containing one plugin.

```
.claude-plugin/marketplace.json     — marketplace manifest (lists the plugin)
plugins/ruflo-stratagent/           — THE PLUGIN (single source of truth)
  .claude-plugin/plugin.json        — plugin manifest
  commands/solve-case.md            — /solve-case entry point
  skills/solve-case/SKILL.md        — engagement orchestrator (the lifecycle brain)
  agents/*.md                       — 7 specialist consultant subagents
  knowledge/frameworks/*.md         — framework cheat sheets per case archetype
  README.md                         — full plugin docs
.claude/agents   -> plugin agents   — symlink, for standalone `claude` dev
.claude/skills   -> plugin skills   — symlink, for standalone `claude` dev
reference/frameworks -> plugin KB   — symlink, for standalone `claude` dev
engagements/                        — per-engagement output artifacts (runtime)
```

The `.claude/*` and `reference/*` entries are **symlinks into the plugin** —
the plugin is the source of truth, and the symlinks let `claude` run in this
repo without installing the plugin. Edit files under `plugins/ruflo-stratagent/`,
never the symlinks.

## How to use it

**As an installed plugin** (from a Claude Code terminal in repo root):
```
/plugin marketplace add .
/plugin install ruflo-stratagent@stratagent
/solve-case <paste a case prompt or describe the business problem>
```

**Standalone** (no install): run `claude` in the repo root and use
`/solve-case ...` directly — the `.claude/` symlinks expose it.

## Architecture (how the system works)

**Orchestrator** — `skills/solve-case/SKILL.md` runs the engagement lifecycle
end to end (classify → scope → frame → analyze → challenge → synthesize →
close out). It is the only thing the user invokes; everything else is a
dispatched subagent.

**Specialist subagents** — `agents/*.md`: `case-classifier`,
`framework-strategist`, `financial-analyst`, `market-analyst`,
`operations-analyst`, `challenger`, `report-writer`. The orchestrator passes
context explicitly and merges results; subagents don't talk to each other.

**Framework library** — `knowledge/frameworks/*.md`, one cheat sheet per
archetype. Read by `case-classifier` and `framework-strategist`; keep these
current rather than hardcoding framework knowledge into agent prompts.

## Built on Ruflo

StratAgent is the **consulting vertical**; Ruflo is the horizontal harness
(orchestration, vector memory, MCP, cost/observability, guardrails, learning).
The orchestrator detects Ruflo's `mcp__claude-flow__*` tools and uses them
(evidence ledger via memory namespaces, swarm dispatch, etc.) when the full
harness is installed (`npx ruflo init`), and falls back to plain files
otherwise. See the "Integration with Ruflo" section of the orchestrator skill
and the plugin README for the full composition map.

## Design principles

- **Evidence over assertion.** Every number traces to a given fact or a labeled
  `[ASSUMPTION: ...]`; the labels survive into the final report.
- **One challenge pass, always.** `challenger` runs on every engagement before
  `report-writer`, not only on request.
- **Frameworks are tools, not scripts.** Adapt/combine frameworks to the actual
  case rather than forcing every case into a memorized template.
