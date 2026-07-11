# StratAgent Roadmap

Direction, not dates. Grounded in the [Research Evaluation](docs/reviews/v1.0-Research-Evaluation.md)
(verdict: *Ready for Limited Beta*) and the tracked technical debt in the
[Operations Runbook §7](docs/operations/Operations-Runbook.md#7-product-evolution).

## Now — `0.1.0-rc2` (Ready for Limited Beta)
- ✅ Full engagement lifecycle, 16 agents, mandatory Reviewer + Challenger gates.
- ✅ Unified knowledge vault (single framework source of truth).
- ✅ Deterministic live validation gate (no report bypasses validation).
- ✅ Evidence-provider extension seam (interface only; none populated).
- ✅ Operational telemetry (schema, sinks, analytics, integration, replay).
- ✅ 954 tests; ruff/black/mypy clean; Operations Runbook + docs.

## Next — toward `1.0` (General Availability)

The single biggest gap is that **every number is an assumption** (the vault holds
no benchmarks by design). Closing that is the headline theme.

1. **Evidence-provider rollout (highest priority).** Implement one concrete
   provider (market data / benchmarks / comparables) on the ADR-007 seam and
   promote `ProviderResult`s into the Evidence Ledger as `external_source`
   records. Turns assumption-heavy output into partially-sourced output.
2. **Telemetry Phase 4.** OTLP exporter `Sink`, dashboard stand-up
   (Engineering / Product / Research / Operations), and the aggregate-then-prune
   retention job. Schema is already OTLP-ready.
3. **Larger genuine evaluation.** n ≥ 12 real engagements (one per archetype)
   for distributional statistics, plus a non-Claude judge to remove the
   shared-model threat.
4. **Determinism affordances.** Seed/version the framework set and record the
   assumption ledger so a re-run is structurally comparable.
5. **Debt paydown.** De-duplicate leaf detection
   (`preconditions.py`/`gates.py`), ratify ADR-001–005, and make live per-agent
   telemetry code-enforced rather than SKILL-instruction-driven.

## Later — enterprise & ecosystem
- Multi-tenant hardening (isolation is scoped by `engagement_id`; add auth +
  privacy review), and a supervised-deployment mode with mandatory human sign-off.
- Deliverable generation beyond Markdown (deck / spreadsheet exports).
- Deeper Ruflo harness integration (swarm dispatch, cross-engagement memory,
  cost/observability) wired end to end after `ruflo init`.

## Non-goals
- Fully autonomous, human-out-of-the-loop recommendations.
- Regulated advice (financial/legal/medical), live trading, or any use where an
  unverified number could cause material harm.

Progress is recorded in [CHANGELOG.md](CHANGELOG.md).
