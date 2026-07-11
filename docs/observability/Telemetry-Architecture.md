# StratAgent Observability — Architecture

**Layer:** operational telemetry · **Package:** `packages/telemetry/` · **Status:**
implemented (library) + designed (LLM integration). Sits alongside the app; adds
**no runtime dependency** and changes no consulting logic.

---

## 1. Where telemetry sits

StratAgent already has a **domain event log** ([state/events.py](../../packages/state/events.py),
ADR-002): ~30 typed events recording *what happened to the engagement*
(`CaseClassified`, `FrameworkSelected`, `ReviewerApproved`, …). Telemetry is a
**separate operational layer** recording *how the machinery performed*
(durations, tokens, retries, validation outcomes). They are **not** merged — the
domain log is the frozen semantic ledger; telemetry is additive observability.
They correlate by **`engagement_id`**.

```
                ┌──────────────────────────────────────────────┐
   engagement   │  DOMAIN EVENT LOG (state/events.py, frozen)  │  semantic "what"
   ─────────────┤  CaseClassified · FrameworkSelected · …      │
        │       └──────────────────────────────────────────────┘
        │  correlate by engagement_id
        ▼       ┌──────────────────────────────────────────────┐
   observability│  TELEMETRY (packages/telemetry, this layer)  │  operational "how"
                │  TelemetryEvent spans · durations · tokens…  │
                └───────────┬──────────────────────────────────┘
                            │ Recorder → Sink
             ┌──────────────┼───────────────┬─────────────────┐
             ▼              ▼               ▼                 ▼
        JSONLSink      MemorySink       MultiSink        (future OTLP)
        (default)       (tests)        (fan-out)        via to_otlp()
                            │
                            ▼
                   analytics.py  → EngagementAnalytics / QualityAnalytics
                            │
                            ▼
              Dashboards (Engineering / Product / Research / Operations)
```

## 2. Components (all in `packages/telemetry/`)

| Module | Responsibility |
|---|---|
| `events.py` | Canonical `TelemetryEvent` schema + `Phase`/`EventStatus`/`ValidationStatus` enums + `to_otlp()` |
| `sink.py` | `Sink` Protocol + `JSONLSink` (append-only, default), `MemorySink`, `NullSink`, `MultiSink` |
| `recorder.py` | `Recorder` — `emit()` + `span()` context manager, sampling, `default_redactor` (privacy) |
| `analytics.py` | Pure aggregation → `engagement_analytics()`, `quality_analytics()` |

## 3. Integration points (design — not wired into agents)

The "agents" are markdown LLM prompts with no code hook, so instrumentation is
**emitted around them**, three ways (this is design guidance; the library is
ready, call sites are not added by this sprint):

1. **Orchestrator spans (primary).** The `solve-case` orchestrator wraps each
   phase dispatch in `recorder.span(engagement_id=…, agent_name=…, phase=…)`. It
   already knows start/finish/phase, so this yields durations, status, and
   retry/rework counts for every agent without touching a `.md` file.
2. **Python component emission (direct).** Deterministic components emit directly:
   - `orchestration.report_gate` → a `VALIDATION_GATE` event with
     `validation_status = PASSED | BLOCKED` (see [API-Contracts](API-Contracts.md)).
   - `governance` gates → review/challenge verdicts as event `metadata.verdict`.
   - `knowledge.retrieve` → a `KNOWLEDGE` event with `metadata.hits`.
3. **Agent telemetry footer (convention).** Each specialist appends a small,
   fenced footer the orchestrator parses into `span.set(confidence=…,
   frameworks_used=[…], tokens=…)`. This carries the fields only the agent knows.
   Footer format is specified in [API-Contracts](API-Contracts.md); it adds no
   consulting logic to the prompt.

Tokens/latency that only the **host** knows (subagent usage blocks) map to
`tokens` / `duration_ms` when available; absence is fine (fields are optional).

## 4. Design principles

- **Additive & non-invasive.** No change to `state`, agents, or consulting logic;
  no new dependency; telemetry off → zero behavior change (`NullSink`).
- **One canonical event.** A single `TelemetryEvent` carries every spec field;
  `status` expresses the agent lifecycle (started/finished/failed/retried/reworked).
- **Structured-only.** No free-form logs; events are typed and JSON-serialized.
  Integrates behind the existing `core/logging.py` seam.
- **Portable.** `to_otlp()` renders OpenTelemetry-compatible spans so an OTLP
  exporter is a new `Sink`, not a rewrite.
- **Privacy by construction.** Redaction bounds metadata; no engagement content
  (report prose, client facts) is persisted — only structural/operational signals.
- **Failure-isolated.** A sink failure never breaks an engagement (`MultiSink`
  swallows per-sink errors; the recorder is best-effort).
