# StratAgent — User Guide

> **Which product is this guide for?** The **Claude Code plugin** (`/solve-case`).
> If you are using the **web dashboard** (`apps/dashboard/`), the consulting
> behaviour below is identical — it runs the same 16 agents and the same
> knowledge vault — but the artifacts stream to your browser instead of landing
> in `engagements/<slug>/`. For setup, see
> [`apps/dashboard/README.md`](../../apps/dashboard/README.md);
> for how the two relate, see
> [ADR-008](../architecture/ADR-008-Repository-Topology.md).

## What StratAgent does

StratAgent runs a complete management-consulting engagement on a business
problem. It is not a chatbot — it is an orchestrated pipeline of specialist
AI agents that mirror a real consulting workflow:

```
Case Classifier → Information Gap → Planner → Framework Selector + Issue Tree Generator
    → Knowledge Agent → Analysts (parallel) → Reviewer → Challenger → Report Writer
    → (optional) Knowledge Curator
```

Each agent is specialized and stateless. The orchestrator (`solve-case`) passes
context explicitly between phases; nothing is assumed to persist between agents.

## Supported case archetypes

| Archetype | Trigger signals |
|---|---|
| Profitability | Margin decline, EBITDA compression, P&L questions |
| Revenue growth | Top-line stagnation, market share, growth strategy |
| Cost reduction | Cost structure, OPEX/COGS reduction targets |
| Pricing | ASP, pricing power, discount analysis |
| Market entry | New geography/segment, launch timing |
| M&A | Acquisition screening, synergy sizing, due diligence |
| New product launch | Go-to-market, feature prioritization |
| Turnaround | Distressed operations, cash runway, restructuring |
| Digital transformation | Tech modernization, AI/data strategy |
| AI strategy | AI adoption, build/buy, ROI |
| Corporate strategy | Portfolio, diversification, M&A pipeline |

## How to invoke

```
/solve-case <problem description>
```

The problem description can be:
- A sentence ("Our margins are down 8pp; help us understand why.")
- A multi-paragraph brief (paste a real client brief or interview prompt)
- A messy data dump (the classifier will extract the real question)

## Engagement phases (RC1 full workflow)

### Phase 1 — Classify
The `case-classifier` reads your brief and produces:
- **Case archetype** (primary + optional secondary)
- **Real question** — the actual diagnostic question, restated precisely
- **Known facts** — what the brief tells us
- **Critical unknowns** — what's missing and whether it's load-bearing

### Phase 1b — Information Gap (if gaps exist)
The `information-gap` agent surfaces load-bearing unknowns. For each:
- Recommends **ask** (pause for human input) or **assume** (proceed with a
  labeled assumption + breakeven threshold)
- Seeds the Assumption Ledger

*You may be asked questions here.* Load-bearing gaps that can't be safely
assumed will be escalated to you before analysis proceeds.

### Phase 2 — Plan
The `planner` produces an ordered execution plan:
- Which analysts to dispatch, in what order
- Which steps can run in parallel
- Dependency chain (e.g., risk-analyst waits for at least one other analyst)

### Phase 3 — Frame
In parallel:
- `framework-selector` selects and adapts frameworks from the vault
- `issue-tree-generator` builds a MECE issue tree (validates MECE before
  committing; self-corrects if violations found)

*A brief checkpoint is surfaced here* so you can redirect the framing if it
looks wrong before analysis runs.

### Phase 4 — Knowledge Retrieval
The `knowledge-agent` retrieves curated vault notes relevant to the case
(framework descriptions, issue tree patterns, KPI benchmarks). These populate
analyst context.

### Phase 5 — Analyze
Specialist analysts run per the plan:
- `financial-analyst` — P&L bridges, unit economics, breakeven, sensitivity
- `market-analyst` — TAM/SAM/SOM, competitive dynamics, demand
- `operations-analyst` — cost structure, process, supply chain, capacity
- `strategy-analyst` — positioning, options, build/buy/partner
- `risk-analyst` — L×I risk register, mitigations, competitive response

Each analyst:
1. Writes only its assigned section of the Engagement State
2. Tags every finding as evidenced (`evidence_refs`) or assumed (`assumption_refs`)
3. Never upgrades an assumption to a fact

### Phase 6 — Review
The `reviewer` checks all analyst work against 5 criteria:
- **MECE** — does the issue tree cover the real question without overlap?
- **Evidence traceable** — every answered finding cites a ref
- **Consistency** — no contradictions across analyst sections
- **Calibration** — confidence scores match evidence quality
- **Gap closure** — critical unknowns from Phase 1b are resolved

If `needs_rework`: the specific implicated analysts are re-dispatched with the
reviewer's issues. Maximum two rework cycles.

### Phase 7 — Challenge
The `challenger` stress-tests the recommendation:
- Tests load-bearing assumptions against their breakeven thresholds
- Constructs the strongest counter-case
- Identifies what information would most change the recommendation
- Checks for competitive blindspots

Verdict:
- `stands` — proceed to report
- `stands_with_caveats` — proceed, caveats preserved in report
- `needs_rework` — specific analysts re-dispatched before proceeding

### Phase 8 — Report
The `report-writer` calls `check_render_ready` to verify both gates are cleared,
then calls `render_report` and writes `engagements/<slug>/report.md`.

The report is structured as:
1. Executive Summary (~150 words; recommendation first)
2. Situation Assessment
3. Framework & Analytical Approach
4. Issue Tree
5. Analysis (one section per analyst)
6. Recommendation (decision + next steps + alternatives rejected)
7. Risks & What Would Change the Answer
8. Implementation Roadmap
9. Appendix A: Assumptions Ledger
10. Appendix B: Evidence References
11. Appendix C: Confidence Scores
12. Appendix D: Knowledge References

### Phase 9 — Knowledge Write-Back (optional)
The `knowledge-curator` extracts up to three durable, generalizable insights
from the engagement and writes them as `draft` notes to `knowledge-vault/`.
This builds the vault over time.

## Understanding the report

### Evidence citations
Every finding in the report is either:
- Backed by evidence: cited inline as `ev_xxx` (full record in Appendix B)
- Assumed: labeled `[ASSUMPTION: ...]` inline (full ledger in Appendix A)

You can audit every claim by tracing `ev_xxx` → Appendix B → source, or
`[ASSUMPTION: ...]` → Appendix A → breakeven threshold.

### The breakeven threshold
Every load-bearing assumption carries a breakeven statement:
*"If X is less than Y, the recommendation inverts."*

This tells you exactly how wrong the assumption would have to be to change
the answer — the most honest signal of recommendation fragility.

### Confidence scores
Appendix C reports confidence by section and overall. These reflect:
- Quality of the evidence (client fact > external source > computed > assumed)
- Validation status (validated vs. unvalidated)
- Number of load-bearing vs. non-load-bearing assumptions

A score of 0.8+ with all load-bearing assumptions validated is strong.
A score below 0.6 signals that more evidence collection would significantly
change the recommendation.

## Rework loops

StratAgent never silently proceeds past a rejected gate:
- Reviewer `needs_rework` → specific analysts re-dispatched → reviewer re-runs
- Challenger `needs_rework` → specific analysts re-dispatched → reviewer + challenger re-run
- After 2 cycles with no progress → escalated to you with a diagnosis

## Framework knowledge base

All frameworks are in `knowledge-vault/frameworks/` (132+ notes). The
`framework-selector` retrieves and adapts them to the case — it never
hardcodes framework knowledge into the analysis.

To add a framework, create a new `framework` type note following ADR-003/ADR-004
frontmatter conventions, set `status: draft`, and it becomes available.

## Troubleshooting

**"Engagement is not complete — no knowledge write-back."**
The knowledge-curator requires a completed engagement with challenger
`stands` or `stands_with_caveats`. If the challenger says `needs_rework`,
resolve the rework issues first.

**Report is missing sections.**
Some sections are optional (e.g., frameworks, issue tree) and are omitted
if the relevant phase didn't run. A minimal state still renders a valid
(if sparse) report.

**Confidence is very low.**
Check Appendix A for load-bearing assumptions without confirmed breakevens.
Consider whether any can be resolved with additional client data before
acting on the recommendation.
