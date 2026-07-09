# StratAgent RC1 — Release Notes

**Version:** 0.1.0-rc1  
**Date:** 2026-07-09  
**Status:** Release Candidate 1

---

## What is RC1?

RC1 is the first feature-complete release of StratAgent. It delivers a full
management-consulting engagement pipeline with:
- 10-phase orchestrated workflow (M4–M6 governance gates, M7 report renderer)
- 15 specialist agents (ADR-005 compliant, stateless, owner-exclusive state writes)
- 861 automated tests (ruff clean, mypy strict)
- A knowledge vault with 132+ curated notes

RC1 is suitable for real consulting use on non-production engagements. It is
not yet a stable API — breaking changes between RC releases are possible.

---

## What's new in RC1

### M7 — Report Generation

**`packages/reporting/renderer.py`** — `render_report(state: EngagementState) → str`
- Pure function, deterministic — same state always produces the same report
- 14 sections: executive summary, situation, frameworks, issue tree, analysis,
  recommendation, risks, roadmap, four appendices (assumptions, evidence,
  confidence, knowledge)
- Every claim is either evidence-backed (cited inline) or labeled `[ASSUMPTION: ...]`
- Footer includes governance gate verdicts and generation timestamp

**`packages/reporting/validation.py`** — structural validation
- `check_render_ready(state)` — 4 anti-hallucination rules enforced before render:
  1. Reviewer gate must be run and approved
  2. Challenger gate must be run and cleared
  3. All answered findings must cite evidence or assumption refs
  4. All load-bearing assumptions must have breakeven thresholds
- `enforce_render_ready(state)` — raises `ReportRenderError` if not ready
- `validate_consistency(state)` — INCOMPLETE_ANALYSIS_BLOCK structural check

### M8 — Evaluation & Validation

- `tests/fixtures/golden_state.py` — `make_golden_profitability_state()`:
  fully-populated, governance-cleared engagement for integration tests
- `tests/integration/test_engagement_lifecycle.py` — 94 tests:
  full state machine, rework loops, forbidden shortcuts, terminal states,
  governance gate preconditions, golden state assertions
- `tests/integration/test_report_generation.py` — 38 tests:
  all 13 section headers, evidence/assumption citations, assumption labeling,
  recommendation body, challenger section, footer, graceful empty handling
- `tests/validation/test_structural_validation.py` — 30 tests:
  all 4 check_render_ready rules, enforce_render_ready, consistency,
  five-section coverage, golden state passes all validators
- `tests/perf/test_m7_bench.py` — M7 performance baselines:
  render_report cold ~82µs, warm ~22µs; check_render_ready ~3µs

### M9 — Production Readiness

- **`knowledge-curator.md`** (new agent) — post-engagement vault write-back:
  extracts up to 3 durable insights and writes `draft` vault notes
- **`report-writer.md`** (updated) — ADR-005 compliance documentation:
  owns exactly `recommendations`, `confidence`, `deliverables`; reads all others
- **`solve-case/SKILL.md`** (updated) — full 10-phase lifecycle including
  all M4-M6 agents (information-gap, planner, framework-selector,
  issue-tree-generator, strategy-analyst, risk-analyst, reviewer, challenger)
- **`docs/guides/QUICKSTART.md`** — 5-minute setup and first engagement
- **`docs/guides/USER_GUIDE.md`** — complete workflow documentation
- **Demo engagement** — `engagements/acme-profitability-demo/` — example
  artifacts for a profitability case

---

## Cumulative since M1

| Milestone | What shipped |
|---|---|
| M1 | Core engagement state (ADR-002), event log, projection, persistence, replay |
| M2 | Knowledge vault (132 notes), frontmatter validator, 28-symbol frozen API |
| M3 | Retrieval adapter (vector + BM25), Knowledge Agent, 74ms benchmark |
| M4 | Planning agents: information-gap, planner, framework-selector, issue-tree-generator; MECE validator, lifecycle precondition gates |
| M5 | Analysis agents: strategy-analyst, risk-analyst; analysis block contract validator |
| M6 | Governance: reviewer, challenger (updated); gate checkers, state machine transitions |
| M7 | Report renderer (14 sections), structural validation (4 rules), 162 new tests |
| M8 | Golden case fixture, integration suite (94 tests), report generation tests (38), structural validation tests (30), M7 benchmarks |
| M9 | knowledge-curator agent, report-writer ADR-005 update, SKILL update, docs, version bump |

**Total tests: 861** | **Total agents: 15** | **Vault notes: 132**

---

## Known limitations in RC1

1. **No web UI** — Claude Code terminal/desktop only.
2. **No real-time data** — market analyst uses web search via Claude tools;
   no structured data feed integration.
3. **Vault notes are `draft`** — promoted to `reviewed` by a human reviewer
   per the Hybrid D-6 authorship policy; not yet peer-reviewed.
4. **Single engagement at a time** — no multi-engagement parallelism in the
   plugin; Ruflo swarm dispatch handles this when the harness is installed.
5. **No authentication/multi-tenancy** — RC1 is local-only; tenant_id is a
   placeholder until the API layer ships.

---

## Upgrade path from M6

RC1 is additive — no state format changes, no breaking API changes:
- All M1–M6 packages frozen and unmodified
- `packages/reporting` is new; no existing code imports it
- New test directories (`tests/fixtures/`, `tests/integration/`,
  `tests/validation/`, `tests/perf/__init__.py`) do not affect existing tests
- `solve-case/SKILL.md` is backward-compatible — old phases still exist

---

## Quality gates (all green at RC1)

- `uv run ruff check packages/ tests/` — 0 errors
- `uv run mypy packages/ --strict` — 0 errors
- `uv run pytest -q` — 861/861 pass
- `render_report` cold-run baseline: ~82µs (well under 100ms target)
