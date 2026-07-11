# StratAgent Observability — Data Storage, Retention & Privacy

Covers the event store, retention, privacy, aggregation, and sampling. Principle:
**collect the minimum operational signal needed; never persist engagement
content.**

---

## 1. Storage layout

- Default sink: **`JSONLSink`** → append-only `telemetry/<engagement_id>.jsonl`,
  one JSON event per line. Matches the repo's file-based, append-only persistence
  ethos; no database, no new dependency.
- One file per engagement → cheap per-engagement reads (`read(id)`) and
  cross-engagement scans (`read_all()`); trivial to archive or delete a single
  engagement.
- Pluggable: an OTLP/HTTP/DB exporter is a drop-in `Sink` (events already render
  via `to_otlp()`); use `MultiSink` to write files **and** export.

## 2. Retention policy

| Tier | Data | Retention | Rationale |
|---|---|---|---|
| Raw events | per-engagement JSONL | **30 days** (default) | debugging / recent analytics |
| Daily aggregates | rolled-up metrics (per Analytics-Definitions) | **13 months** | trends, dashboards, GA evidence |
| Incident captures | events for a flagged failed engagement | **90 days** | root-cause |

Process: **aggregate, then prune.** A scheduled job computes daily aggregates,
writes them to the aggregate store, then deletes raw JSONL older than the raw-tier
TTL. (The library ships the read/aggregate functions; the scheduler is an
operational deployment concern, out of scope for this sprint.)

## 3. Privacy

- **No engagement content is stored.** Telemetry persists structural/operational
  signals only (phase, status, durations, counts, verdicts, confidence). Report
  prose, client facts, and problem text never enter an event.
- **`metadata` is bounded by `default_redactor`:** drops keys starting with `_`,
  truncates strings to 256 chars, caps to 32 keys, caps list items, and **rejects
  nested mappings** (which could smuggle unbounded/sensitive payloads).
- **No PII in identifiers or paths.** File names use only `engagement_id` (a
  system id); the path builder is escape-safe (`../`, `/` neutralized).
- **Tenant isolation.** `engagement_id` is tenant-scoped upstream; aggregates
  should be filtered by tenant before cross-tenant reporting.
- **Right to deletion.** Deleting one engagement's telemetry is a single file
  removal; document it in the data-deletion runbook.
- **Do not collect unnecessarily.** `tokens` and `confidence` are optional; if a
  deployment does not want cost or model-confidence retained, omit them at emit.

## 4. Aggregation

- Dashboards read **aggregates**, not raw events, for anything cross-engagement.
- Aggregation is via the pure `quality_analytics` / `engagement_analytics`
  functions — deterministic and side-effect-free, so aggregates are reproducible
  from retained raw data within the raw-tier window.
- **Small-n rule** (carried from the research evaluation): any aggregate cell with
  n < 8 is reported as a raw count, never a rate — no false precision.

## 5. Sampling

- `Recorder(sample_rate=…)` drops a fraction of spans deterministically via an
  injectable sampler. Default `1.0` (capture all) for beta; lower it under high
  volume.
- Sampling is decided at span entry, so a span's START and FINISH are dropped or
  kept **together** (no orphan events).
- **Never sample out failures/blocks** in production configs — sample the happy
  path, keep every `failed`/`blocked` (recommended config, not enforced by the
  library; wire via a status-aware sampler or a `MultiSink` where errors go to an
  unsampled recorder).

## 6. Security notes

- Sinks are best-effort and failure-isolated (`MultiSink` swallows per-sink
  errors) so telemetry can never break or slow an engagement.
- The event store is append-only; there is no update/delete path in the library
  (deletion is a filesystem/ops action, auditable).
