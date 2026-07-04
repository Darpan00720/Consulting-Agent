---
title: Performance Baselines (consolidated)
status: Baseline — M1.7.7
date: 2026-07-04
supersedes: docs/performance/projection-baseline.md (M1.5 original, kept for history)
relates: [tests/perf/*]
---

# Performance Baselines

The single consolidated record of measured baselines for the state layer:
projection, validation, the append write path, snapshot reads, and replay
verification. **These are regression references, not targets.** The standing
policy since M1.5 holds: no optimization without a measurement that justifies
it. No benchmark asserts a latency threshold — each asserts only that the
operation ran.

## Benchmark environment
| | |
|---|---|
| Commit | `bfcf042` (+ the M1.7.7 benchmark harness) |
| Machine | Apple M3, 8 cores |
| OS | macOS 26.5.1 (Darwin arm64) |
| Python | 3.12.13 (uv-managed) |
| pytest-benchmark | 5.2.3 |
| Date | 2026-07-04 |

## Benchmark methodology
- **Harness:** `pytest-benchmark`, `benchmark.pedantic(fn, rounds=1,
  iterations=1)` — a single measured **cold** run per scale. Run in-suite
  (`tests/perf/`, or `make bench`).
- **Warm-up policy:** none — cold single run by design (keeps the suite fast
  and the numbers comparable across milestones).
- **Iteration count:** 1 round × 1 iteration per parameter.
- **Scales:** 10 / 100 / 1,000 / 10,000 (batch append: 10 / 100 / 1,000).
- **Fixtures:** append/snapshot states and replay logs are built by appending
  an `EngagementCreated`-led event log through the real pipeline, so the
  measured object is genuine.

> **Limitations (read before citing a number).** Single-run ⇒ real run-to-run
> variance, especially at small N where fixed overhead dominates (±30–50% is
> normal; e.g. validation@10 and @100 can invert between runs). Numbers are
> machine-specific (Apple M3) and order-of-magnitude only — they exist to
> catch **gross** regressions, not to certify micro-optimizations.

## Measured baselines

### Append write path
| Operation | Complexity (M1.7-Design §7) | 10 | 100 | 1,000 | 10,000 |
|---|---|---|---|---|---|
| `append_event` (state size) | O(\|state\|), log-independent | ~25 µs | ~27 µs | ~83 µs | ~1.05 ms |
| `append_events` (batch size) | O(k·apply) + one validation | ~66 µs | ~524 µs | ~6.3 ms | — |

### Snapshot read
| Operation | Complexity | 10 | 100 | 1,000 | 10,000 |
|---|---|---|---|---|---|
| `get_state` (state size) | O(\|state\|) deep copy (D1) | ~88 µs | ~451 µs | ~4.6 ms | ~72.7 ms |

### Replay verification
| Operation | Complexity (M1.7.4 §7) | 10 | 100 | 1,000 | 10,000 |
|---|---|---|---|---|---|
| `verify_log` (log size) | O(n) single pass | ~5.5 µs | ~16 µs | ~154 µs | ~1.6 ms |
| `verify_pair` (log size) | O(n) | ~4.1 µs | ~17 µs | ~152 µs | ~1.8 ms |

### Validation (TD-010 — baseline previously unpublished)
| Operation | Complexity | 10 | 100 | 1,000 | 10,000 |
|---|---|---|---|---|---|
| `validate` (object count) | O(\|state\|) | ~56 µs | ~44 µs | ~328 µs | ~4.2 ms |

### Projection (from M1.5; re-measured here for one coherent set)
| Operation | Complexity | 10 | 100 | 1,000 | 10,000 |
|---|---|---|---|---|---|
| `project` (event count) | ~linear, mild superlinear | ~95 µs | ~339 µs | ~3.4 ms | ~53.7 ms |

(The M1.5 original `projection-baseline.md` is kept for history; its numbers
are a different single-run and differ within variance.)

## Interpretation
- **`append_event` is validation-dominated and log-independent** — it stays
  well under ~100 µs to 1,000 objects and ~1 ms at 10,000, tracking the
  validation cost of the post-state rather than the log length. This is the
  design's headline O(\|state\|) claim, confirmed.
- **`append_events` folds k events + validates once** — its cost is ≈ k
  incremental applies plus a single validation, so a 1,000-event batch (~6.3
  ms) is far cheaper than 1,000 separate appends would be.
- **`get_state` is the most expensive read at scale** (~73 ms at 10,000
  objects) — the deliberate O(\|state\|) deep-copy price of snapshot isolation
  (design D1). At engagement scale (≤ ~1,000 objects) it is ~4.6 ms. If large
  states ever make this hurt, copy-on-write is the pre-identified lever —
  measured first, per policy.
- **Replay verification is cheap and linear** (~1.6–1.8 ms at 10,000 events),
  run once per load/replay — negligible against the fold it guards.
- **All operations are comfortably sub-millisecond at engagement scale**
  (hundreds to low thousands of objects/events), which is the regime ADR-002
  targets.

## Scope notes
Deliberately **not** benchmarked (M1.7.7 design, approved): `project` beyond the
row above (already baselined in M1.5); the O(1) operations `current_version` /
`current_sequence` / conflict detection (noise-dominated micro-timings);
`make traceability` (a dev-time script, no runtime surface); ownership-dataset
lookup (frozen module constants, no consumer until M6).
