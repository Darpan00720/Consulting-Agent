# StratAgent RC1 — Quick Start

**StratAgent** is an AI management-consulting platform built on Claude Code.
Paste a business problem and it runs a full engagement lifecycle: classify →
plan → frame → analyze → review → challenge → report.

## Prerequisites

- Claude Code (CLI or desktop app)
- Python 3.12+ with `uv` (`pip install uv`)

## Option A — Standalone (no install)

1. Clone or open this repository in Claude Code.
2. Run `uv sync` once to install Python dependencies.
3. Open the agent panel and type:

```
/solve-case Our operating margin has dropped 8pp this year. Revenue is roughly
flat but costs have spiked. The board wants a diagnosis and a plan.
```

The orchestrator will run all phases and write the report to
`engagements/<slug>/report.md`.

## Option B — Plugin install (full Ruflo harness)

```bash
/plugin marketplace add .
/plugin install ruflo-stratagent@stratagent
/solve-case <your problem>
```

## What you get

Every engagement produces:

| File | Contents |
|---|---|
| `01-intake.md` | Case classification, known facts, critical unknowns |
| `01b-gaps.md` | Information-gap analysis and ask-vs-assume decisions |
| `02-plan.md` | Ordered execution plan with parallel groups |
| `03-framework.md` | Selected frameworks with adaptation rationale |
| `03-issue-tree.md` | MECE issue tree (validated) |
| `04-knowledge.md` | Vault references retrieved for this case |
| `05-*.md` | Individual analyst outputs |
| `06-review.md` | Reviewer verdict (approved / needs_rework) |
| `07-challenge.md` | Challenger verdict (stands / stands_with_caveats / needs_rework) |
| `report.md` | Final executive-ready report |

## Example cases

- **Profitability:** `engagements/acme-profitability-demo/` — see the demo
  included in this repo.
- **Market entry, pricing, M&A** — just describe the problem; the
  `case-classifier` determines the archetype automatically.

## Interpreting the report

Every number in the report is either:
- Backed by a cited evidence record (`ev_xxx`) — labeled in Appendix B
- An `[ASSUMPTION: ...]` — catalogued with its breakeven in Appendix A

The report is only generated after both governance gates clear:
- Reviewer: `approved`
- Challenger: `stands` or `stands_with_caveats`

If challenger says `needs_rework`, the engagement halts and tells you what to fix.

## Next steps

- See [USER_GUIDE.md](USER_GUIDE.md) for complete workflow documentation.
- See the [RC1 Release Notes](../reviews/RC1-Release-Notes.md) for what's
  included in this release.

## Observability (optional)

Every engagement can emit an operational telemetry trace (durations, tokens,
retries, governance verdicts) — separate from the report, correlated by
`engagement_id`. It writes `telemetry/<engagement_id>.jsonl`.

```bash
# summarize one engagement (durations by phase, confidence, frameworks)
uv run python scripts/engagement_telemetry.py --engagement <engagement_id>

# quality metrics across all engagements (reviewer pass rate, challenger intervention…)
uv run python scripts/engagement_telemetry.py --all --quality

# see worked sample traces from the three pilots
uv run python scripts/replay_pilots.py   # → docs/observability/samples/
```

Full design: [docs/observability/](../observability/Telemetry-Architecture.md).
Telemetry never blocks or changes an engagement; disable it and behaviour is
identical.
