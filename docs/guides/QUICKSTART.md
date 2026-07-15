# StratAgent — Quick Start

**StratAgent** is an AI management-consulting platform. Paste a business problem
and it runs a full engagement lifecycle: classify → plan → frame → analyze →
reconcile → review → challenge → report.

It ships in two forms that run **the same 16 agents and the same knowledge
vault**. Pick whichever fits — the web dashboard needs no Claude Code.

---

## Option A — Web dashboard (fastest; Docker only)

No API key, no signup, no Claude Code. Mock mode runs the whole lifecycle with
canned outputs so you can see it work in seconds:

```bash
cd apps/dashboard
STRATAGENT_MOCK=1 docker compose up --build     # → http://localhost:3000
```

For **real** engagements, add at least one free provider key to
`apps/dashboard/.env` and drop the `STRATAGENT_MOCK=1`:

```bash
GEMINI_API_KEY=AIza...       # https://aistudio.google.com/apikey  (best free tier)
CEREBRAS_API_KEY=csk-...     # https://cloud.cerebras.ai           (optional)
```

Any subset works. A real run takes ~5–7 minutes; if every provider hits its rate
limit the engagement **pauses and auto-resumes** instead of failing. You can also
paste your own key (Anthropic / OpenAI / OpenRouter / Cerebras / Groq / Google)
into the UI — used for that run only, never stored.

Full options: [`apps/dashboard/README.md`](../../apps/dashboard/README.md).

---

## Option B — Claude Code, standalone (no install)

Prerequisites: Claude Code (CLI or desktop) and Python 3.12+ with `uv`.

1. Clone or open this repository in Claude Code.
2. Run `uv sync` once to install Python dependencies.
3. Open the agent panel and type:

```
/solve-case Our operating margin has dropped 8pp this year. Revenue is roughly
flat but costs have spiked. The board wants a diagnosis and a plan.
```

The orchestrator will run all phases and write the report to
`engagements/<slug>/report.md`.

## Option C — Plugin install (full Ruflo harness)

```bash
/plugin marketplace add .
/plugin install ruflo-stratagent@stratagent
/solve-case <your problem>
```

> Options B and C produce the per-phase files listed below. **Option A** keeps
> the same artifacts in its database and streams them to the browser instead.

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

If a gate does not clear, StratAgent **does not ship a recommendation**. You get
an honest interim status report, clearly flagged as not final, listing exactly
what must be reconciled. That refusal is the design, not a failure.

## Next steps

- See [USER_GUIDE.md](USER_GUIDE.md) for complete workflow documentation.
- See the [CHANGELOG](../../CHANGELOG.md) for what's in the current release.
- See [ADR-008](../architecture/ADR-008-Repository-Topology.md) if you plan to
  contribute — it says which of the repo's three artifacts to edit.

## Observability (optional)

Every engagement can emit an operational telemetry trace (durations, retries,
governance verdicts) — separate from the report, correlated by `engagement_id`.
One JSONL file per engagement.

**The dashboard emits this automatically** (since 1.0.0-beta.1) to
`$STRATAGENT_TELEMETRY_DIR`, which defaults to a `telemetry/` directory beside
its database — inside Docker that is `/app/data/telemetry/`. Copy it out and
point the same CLI at it with `--root`:

```bash
# summarize one engagement (durations by phase, confidence, frameworks)
uv run python scripts/engagement_telemetry.py --engagement <engagement_id> --root <dir>

# quality metrics across engagements (reviewer pass rate, challenger intervention…)
uv run python scripts/engagement_telemetry.py --all --quality --root <dir>

# see worked sample traces from the three pilots
uv run python scripts/replay_pilots.py   # → docs/observability/samples/
```

Real output from a dashboard run — this is what tells you where time actually
goes (review was nearly as expensive as all five analysts):

```json
"duration_by_phase_ms": { "analysis": 78462, "review": 67923, "planning": 11538 },
"reviewer_pass_rate": 1.0, "validation_block_rate": 0.5
```

Full design: [docs/observability/](../observability/Telemetry-Architecture.md).
Telemetry never blocks or changes an engagement; disable it and behaviour is
identical.
