---
title: Projection Performance Baseline
status: Baseline (M1.5)
date: 2026-06-30
relates: [packages/state/projection.py, tests/perf/test_projection_bench.py]
tags: [performance, projection, baseline]
---

# Projection Performance Baseline

> **Superseded (M1.7.7):** the consolidated authority is now
> [`baselines.md`](baselines.md), which covers projection alongside validation,
> the append path, snapshots, and replay. This M1.5 document is retained for
> history.

Recorded baseline timings for `state.projection.project` (folding an event log into an
`EngagementState`). These are **indicative regression references, not optimization
targets** — per the M1.5 constraint, projection is not optimized unless a measurement
proves unacceptable.

## Benchmark environment
| | |
|---|---|
| Machine | Apple M3, 8 cores |
| OS | macOS 26.5.1 (Darwin arm64) |
| Python | 3.12.13 (uv-managed) |
| pytest-benchmark | 5.2.3 |
| Date | 2026-06-30 |

## Benchmark methodology
- **Harness:** `pytest-benchmark`, `benchmark.pedantic(project, args=(log,), rounds=1,
  iterations=1)` — a single measured (cold) run per scale, run as part of the
  automated suite (`tests/perf/test_projection_bench.py`).
- **Workload:** one `EngagementCreated` followed by a mixed log cycling five event
  types (`EvidenceAdded`, `AssumptionAdded`, `InformationGapIdentified`,
  `FrameworkSelected`, `PhaseTransitioned`). Mixing spreads list appends across
  sections rather than hammering a single collection (more representative).
- **Caveat:** single-run (`rounds=1`) means run-to-run variance is expected
  (roughly ±30–50% at small N — fixed overhead dominates). These are order-of-magnitude
  baselines to catch gross regressions, **not** statistically rigorous micro-benchmarks.

## Event counts & measured timings
Representative run on the environment above:

| Events | Mean time | ~ per event |
|---|---|---|
| 10 | ~98 µs | ~9.8 µs |
| 100 | ~155 µs | ~1.6 µs |
| 1,000 | ~1.56 ms | ~1.6 µs |
| 10,000 | ~32.9 ms | ~3.3 µs |

(Current numbers print in the `make check` / benchmark output; the table above is a
snapshot, not a pinned assertion.)

## Interpretation
- Growth is roughly linear with a mild superlinear component: the immutable reducer
  rebuilds a collection on each append (shallow, structural-sharing copies), so
  repeated appends to the *same* collection are O(n²) worst-case. The mixed workload
  keeps 10,000 events at ~33 ms — well within bounds for engagement-scale logs
  (hundreds to low thousands of events).
- **No optimization has been performed.** If real engagements ever approach
  unacceptable projection latency, candidate optimizations (structural-sharing list
  types, builder accumulation, periodic snapshots) become justified — measured first,
  per the M1.5 principle.
