# StratAgent Execution Flow (post-RC1.2)

How a live engagement actually executes, and where the deterministic guards sit.
Reflects the RC1.2 convergence (ADR-006, ADR-007).

## Orchestration model

An engagement is an **LLM-orchestrated** run of the `solve-case` skill, which
dispatches specialist subagents. Deterministic Python (`packages/`) provides the
validators, gates, and the report gate the orchestrator must call.

## Phase flow

```
/solve-case <problem>
   │
   ▼
Phase 0  setup  ──────────────  frameworks come from ONE source:
   │                            knowledge-vault/frameworks/ (ADR-003/004)
   ▼
Phase 1  case-classifier      ─ names archetype(s); no framework store of its own
Phase 1b information-gap      ─ seeds load-bearing assumptions + breakevens
Phase 2  planner
Phase 3  framework-selector ∥ issue-tree-generator   (vault retrieval; MECE-validated)
Phase 4  knowledge-agent      ─ retrieve() over knowledge-vault
Phase 5  analysts (financial / market / operations / strategy / risk)
   │
   ▼
Phase 6  REVIEWER  ◀── MANDATORY in every mode (ADR-006). Not skippable.
   │        │ needs_rework → re-dispatch analyst(s) → re-review (≤2 cycles)
   ▼
Phase 7  CHALLENGER ◀── MANDATORY. needs_rework → rework loop → re-challenge
   │
   ▼
Phase 8a  LIVE VALIDATION GATE  ◀── NEW (ADR-006)
   │        emit engagements/<slug>/state.json
   │        uv run python scripts/validate_engagement.py <slug>
   │        runs enforce_render_ready + validate_consistency
   │        ├─ exit 0 → proceed
   │        └─ exit 1 → BLOCK: read diagnostics, route to owning agent, fix, re-run
   ▼
Phase 8b  report-writer  ─ writes report.md (gate, not the writer, is the authority)
   │
   ▼
Phase 9  knowledge-curator (optional)   Phase 10  close out
```

## The two convergence guards

### Framework source of truth (WI-1)
Every framework-consuming agent (classifier, planner, framework-selector,
knowledge-agent) resolves frameworks through `knowledge-vault/frameworks/` via
the retrieval adapter. The plugin's old `knowledge/frameworks/*.md` cheat sheets
are deprecated redirect stubs (`_MIGRATION.md` holds the archetype index).

### Deterministic report gate (WI-2)
Before any report is delivered, the orchestrator serializes the engagement to
`state.json` and runs the blocking gate in `packages/orchestration/`. The gate
runs the `reporting` anti-hallucination checks:
- **render-ready:** both governance verdicts present + cleared; every answered
  finding cites evidence or an assumption; load-bearing assumptions have
  breakevens.
- **consistency:** no COMPLETE analysis block has an unanswered finding.

Failure blocks report generation and emits `(check:rule) [section] detail`
diagnostics. No report may bypass the gate.

## What stays out of the live path

`render_report(state)` (the deterministic Markdown renderer) is available but is
**not** the live report author — the LLM `report-writer` writes the narrative.
The gate validates structure; the writer supplies prose. Evidence Providers
(ADR-007) are an attachable seam and are not wired into retrieval by default.
