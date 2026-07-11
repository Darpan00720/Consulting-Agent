# StratAgent Observability — Analytics Definitions

Every metric, its formula, and its source. Computed by pure functions in
[analytics.py](../../packages/telemetry/analytics.py). "From stream" = derived
from telemetry events directly; "from metadata" = read from a well-known
`metadata` key an emitter populated.

---

## Engagement analytics (`engagement_analytics(events) → EngagementAnalytics`)

Per engagement (events sharing one `engagement_id`).

| Metric | Definition | Source |
|---|---|---|
| `event_count` | Number of telemetry events | stream |
| `total_wall_ms` | `max(timestamp) − min(timestamp)` | stream |
| `active_ms` | Σ `duration_ms` of FINISHED events | stream |
| `duration_by_phase_ms` | Σ `duration_ms` grouped by `phase` | stream |
| `rework_count` | count(`status == reworked`) | stream |
| `validation_failures` | count(`validation_status == blocked`) | stream |
| `knowledge_retrieval_hits` | Σ `metadata.hits` over KNOWLEDGE events | metadata |
| `frameworks_used` | ∪ `frameworks_used` across events | stream |
| `confidence` | distribution summary of all `confidence` values | stream |
| `issue_tree_size` | latest `metadata.issue_tree_size` | metadata |
| `recommendation_count` | latest `metadata.recommendation_count` | metadata |

Per-phase durations directly answer the spec's *planning / analysis / report /
review / challenge duration* asks (each is a `Phase` key in `duration_by_phase_ms`).

## Quality analytics (`quality_analytics(events) → QualityAnalytics`)

Across many engagements.

| Metric | Definition | Source |
|---|---|---|
| `reviewer_pass_rate` | approved ÷ terminal REVIEW events | metadata.verdict == "approved" |
| `challenger_intervention_rate` | (stands_with_caveats ∪ needs_rework) ÷ terminal CHALLENGE events | metadata.verdict |
| `needs_rework_frequency` | needs_rework ÷ (REVIEW ∪ CHALLENGE terminal events) | metadata.verdict / status |
| `validation_block_rate` | blocked ÷ events with a `validation_status` | stream |
| `framework_selection_frequency` | count of each framework across `frameworks_used` | stream |
| `knowledge_retrieval_effectiveness` | fraction of KNOWLEDGE events with `hits > 0` | metadata.hits |
| `assumption_count_total` | Σ per-engagement `metadata.assumption_count` | metadata |
| `unsupported_finding_count_total` | Σ per-engagement `metadata.unsupported_finding_count` | metadata |
| `evidence_count_total` | Σ per-engagement `metadata.evidence_count` | metadata |
| `confidence` | distribution summary across all events | stream |

## Confidence distribution (`summarize_confidence(values) → ConfidenceSummary`)

`n`, `mean`, `median`, `minimum`, `maximum`, and coarse histogram `buckets`
(`0.0-0.5`, `0.5-0.7`, `0.7-0.9`, `0.9-1.0`). Used for the "confidence
distribution" and "confidence calibration" views.

## Notes on honesty

- **Content metrics depend on emitters.** `assumption_count`,
  `unsupported_finding_count`, `issue_tree_size`, and `evidence_count` are
  engagement *content* — their source of truth is `EngagementState`. Telemetry
  reports them only when an emitter snapshots them into `metadata` (e.g. the
  report gate emits state counts). Missing key → the metric is simply absent, not
  guessed.
- **Rates return `None`, not 0, when the denominator is empty** — so a dashboard
  can distinguish "0%" from "no data yet."
- **`_sum_meta` counts once per engagement** to avoid double-counting a content
  snapshot repeated across an engagement's events.
