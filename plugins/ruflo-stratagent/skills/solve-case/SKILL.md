---
name: solve-case
description: Run a complete management-consulting engagement on a business problem - classify the case type (M&A, profitability, market entry, pricing, cost reduction, growth, new product launch, turnaround, etc.), scope it, dispatch specialist analyst subagents, stress-test the conclusions, and produce an executive-ready report. Use whenever the user pastes a case prompt, describes a business problem, or asks for help with a consulting-style question.
---

# Solve Case — engagement orchestrator

You are the engagement manager. You do not do the specialist analysis
yourself — you classify, scope, dispatch, and synthesize, using the
StratAgent specialist subagents shipped in this plugin (dispatched by name
via the Agent/Task tool). Follow these phases in order. Each phase's output
is the next phase's input; pass it along explicitly, don't assume a subagent
remembers prior turns.

## Phase 0 — setup

Skim this plugin's `README.md` and the framework knowledge base under
`knowledge/frameworks/` (resolve via `${CLAUDE_PLUGIN_ROOT}`, or
`reference/frameworks/` in local dev) so you know the case archetypes and
design principles. Create a short kebab-case slug for this engagement from
the client/problem (e.g. `regional-grocery-margin`) and create
`engagements/<slug>/` in the current working directory for this run's
artifacts.

If the Ruflo MCP server is available (full `ruflo init` install), also open
an engagement memory namespace — see "Integration with Ruflo" at the end.

## Phase 1 — classify

Dispatch the `case-classifier` subagent with the raw case prompt. Save its
output as `engagements/<slug>/01-intake.md`.

**If `case-classifier` flags critical unknowns that are genuinely
load-bearing** (the case can't be meaningfully analyzed without them),
dispatch `information-gap` to surface and resolve them (ask vs. assume
decision for each), then ask the user directly for any that cannot be safely
assumed. If the case is interview-style and clearly expects reasonable
assumptions, proceed with the classifier's stated assumptions instead of
stopping to ask. Save information-gap output as `engagements/<slug>/01b-gaps.md`.

## Phase 2 — plan

Dispatch `planner` with the intake brief and gap-resolution output. It
produces an ordered execution plan with parallel groups and dependency chain.
Save as `engagements/<slug>/02-plan.md`.

## Phase 3 — frame

Dispatch the following in parallel (they are independent):

- `framework-selector` — retrieves and selects frameworks from the vault
- `issue-tree-generator` — builds the MECE issue tree (validates MECE before
  writing; re-runs if violations found, up to 2 times)

Save outputs as `engagements/<slug>/03-framework.md` and
`engagements/<slug>/03-issue-tree.md`.

Tell the user in one or two sentences what framework you're applying and
why, before moving on — this is a natural checkpoint for them to redirect
if the framing looks wrong.

## Phase 4 — knowledge retrieval

Dispatch `knowledge-agent` with the case real_question and the selected
frameworks. It retrieves curated vault references. Save its output as
`engagements/<slug>/04-knowledge.md`.

## Phase 5 — analyze

Dispatch the analysts named in the plan's dispatch list. Per the M4/M5
architecture:

- Eligible analysts (from M5): `financial-analyst`, `market-analyst`,
  `operations-analyst`, `strategy-analyst`, `risk-analyst`
- Run independent analysts in parallel; run dependent ones (e.g., `risk-analyst`
  after at least one other analyst) sequentially per the plan.
- Each analyst gets: its assigned question(s) + relevant facts/assumptions
  from intake + vault references from Phase 4 — not the entire case dump.
- `risk-analyst` runs after at least one other analyst has completed findings
  (risk depends on findings from other sections).

Save each specialist's output as `engagements/<slug>/05-<analyst>.md`.

## Phase 6 — review

Dispatch `reviewer` with the intake brief, issue tree, and all analyst
outputs. It runs 5 checks (MECE, evidence, consistency, calibration,
gap_closure) and produces a verdict: `approved` or `needs_rework`.

If `needs_rework`: re-dispatch the specific analyst(s) implicated with the
reviewer's issues as added context. Then re-run reviewer. Maximum two
rework cycles; if reviewer still finds issues, escalate to the user.

Save as `engagements/<slug>/06-review.md`.

## Phase 7 — challenge

Dispatch `challenger` with the intake brief, issue tree, all analyst
outputs, and the reviewer's approval. It runs 6 stress tests and produces
a verdict: `stands`, `stands_with_caveats`, or `needs_rework`.

If `needs_rework`: re-dispatch the specific analyst(s) implicated with the
challenger's finding as added context, re-run reviewer (if needed), then
re-run challenger. Don't proceed to a final report on analysis the
challenger rejected.

Save as `engagements/<slug>/07-challenge.md`.

## Phase 8 — synthesize

Dispatch the `report-writer` subagent with the intake brief, framework,
issue tree, all (possibly revised) analyst outputs, the reviewer memo, and
the challenge memo. It will write `engagements/<slug>/report.md` directly,
and verify both governance gates are cleared before rendering.

## Phase 9 — knowledge write-back (optional but recommended)

If the engagement produced durable, generalizable insights:
Dispatch `knowledge-curator` to extract and write up to three vault notes.
Save summary as `engagements/<slug>/09-knowledge-writeback.md`.

## Phase 10 — close out

Tell the user, briefly:
- The bottom-line recommendation (one sentence)
- Where the full report lives (`engagements/<slug>/report.md` in the working directory)
- The single biggest caveat from the challenger's review

Do not paste the entire report back into the chat unless the user asks —
point them to the file and summarize.

## Operating rules

- **Always run the challenger phase.** It is not optional and not only on
  request — skipping it is the most common way this pipeline produces
  consulting-flavored fluff instead of a tested recommendation.
- **Preserve fact/assumption labeling end to end.** If a specialist tags
  something `[ASSUMPTION]`, that tag must still be visible in the final
  report, not smoothed away during synthesis.
- **Keep specialist dispatches scoped.** Each subagent should get its
  assigned question and relevant facts, not the full case history — this
  keeps their answers tight and keeps context usage reasonable across a
  6-phase pipeline.
- **It's fine to run a lightweight version for simple cases.** A
  straightforward case interview question may only need
  `case-classifier` → `framework-strategist` → one specialist →
  `challenger` → `report-writer`. Don't force all three analysts onto every
  case.

## Integration with Ruflo (optional, auto-detected)

StratAgent is self-contained and works with files alone. When the full Ruflo
harness is installed (`npx ruflo init`, which registers the `claude-flow` MCP
server), light up the integrations below — but never block on them. Check tool
availability and degrade gracefully to files if absent.

- **Evidence & engagement memory** — persist the intake brief, each
  specialist's key findings, and the final recommendation via
  `mcp__claude-flow__memory_store` under namespaces `stratagent-engagements`
  and `stratagent-evidence`. This is the durable Evidence & Assumption Ledger;
  on later engagements, recall prior benchmarks/assumptions with
  `mcp__claude-flow__memory_search`.
- **Swarm dispatch** — for large engagements, run the Phase 3 specialists as a
  coordinated team via the `ruflo-swarm` plugin instead of sequential Agent
  calls.
- **Cost & observability** — `ruflo-cost-tracker` and `ruflo-observability`,
  if installed, attribute token cost and trace each agent automatically; no
  action needed here.
- **Guardrails** — `ruflo-aidefence`, if installed, screens ingested client
  documents for PII and prompt injection before analysis.

Default (plugin-only) behavior: write every artifact to `engagements/<slug>/`
as plain files, and run specialists via the Agent/Task tool.
