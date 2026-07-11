# StratAgent Observability — Dashboard Design

Four dashboards, one per audience. Each shows **only** what that audience acts on.
All metrics are computed from the telemetry stream via
[analytics.py](../../packages/telemetry/analytics.py) (see
[Analytics-Definitions](Analytics-Definitions.md)); no dashboard needs raw event
access.

Conventions: **p50/p90** = median / 90th percentile; a rate shown as "—" means no
data yet (rates return `None`, not 0).

---

## 1. Engineering — "is the machine healthy and fast?"

| Panel | Metric | Alert |
|---|---|---|
| Phase latency | p50/p90 `duration_by_phase_ms` per phase | p90 analysis > 15 min |
| Failure rate | `status == failed` ÷ terminal events, by agent | > 5% for any agent |
| Retry & rework | Σ `retry_count`, `rework_count` per engagement | rework > 2 / engagement |
| Validation blocks | `validation_block_rate` | trending up |
| Token cost | Σ `tokens` per engagement + per phase | p90 > budget |
| Slow-span outliers | top-N events by `duration_ms` | the ~22-min risk-analyst class |

## 2. Product — "are users getting value?"

| Panel | Metric | Watch |
|---|---|---|
| Volume | engagements/day; completion rate (`finished` reaching REPORTING) | completion < 90% |
| Time-to-recommendation | wall-clock intake→reporting (p50/p90) | rising |
| Archetype mix | engagements by classified archetype | coverage gaps |
| Framework usage | `framework_selection_frequency` (top 10) | over-reliance on one |
| Confidence distribution | `confidence.buckets` | mass in 0.9–1.0 = overconfidence risk |
| Drop-off | engagements abandoned by phase | early-phase drop |

## 3. Research — "is the consulting good and well-governed?"

| Panel | Metric | Signal |
|---|---|---|
| Reviewer pass rate | `reviewer_pass_rate` | too high = rubber-stamp; too low = weak analysts |
| Challenger intervention | `challenger_intervention_rate` | the differentiator — expect meaningful > 0 |
| Needs-rework frequency | `needs_rework_frequency` | governance actually firing |
| Evidence vs. assumptions | `evidence_count_total` vs `assumption_count_total` | the empty-vault gap, quantified |
| Unsupported findings | `unsupported_finding_count_total` | should trend to 0 (gate blocks them) |
| Calibration | `confidence` summary per archetype | mismatch vs. reviewer outcome |
| Per-archetype quality | rework/verdict rates sliced by archetype | soft archetypes (org design) lag |

## 4. Operations — "what's happening right now?"

| Panel | Metric | Action |
|---|---|---|
| Active engagements | count of engagements with no terminal REPORTING event | capacity |
| In-flight phase | latest phase per active engagement | stuck detection |
| Recent failures/blocks | `failed` + `blocked` in last 1h | page on spike |
| Latency SLO | % engagements under time budget | SLO breach |
| Cost burn | Σ `tokens` in last 1h × price | budget guardrail |
| Error feed | stream of `status == failed` with agent + phase | triage |

---

## Cross-cutting

- Every panel is **sliceable by** `engagement_id`, `agent_name`, `phase`,
  archetype (from metadata), and time window.
- **Small-n honesty** (carried from the research eval): a slice with n < 8 shows
  the raw count, not a rate — dashboards must not imply precision that isn't there.
- Dashboards are **read-only views**; the source of truth is the JSONL event store
  (or the OTLP backend once exported).
