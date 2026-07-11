# StratAgent Observability — Implementation Plan

Phased rollout. **Phases 0–2 are built and tested**; Phase 3 is intentionally
avoided (agent prompts untouched); Phase 4 (export infra + dashboards) is future.
No consulting logic or agent behaviour was modified in any phase.

> **Integration sprint status (v1.0):**
> - **Phase 0 ✅** — telemetry library.
> - **Phase 1 ✅** — `EngagementTracer` + `scripts/record_telemetry.py`; the
>   `solve-case` SKILL now records a span per dispatch; `orchestration.record_gate`
>   / `instrument_gate` emit the validation-gate event.
> - **Phase 2 ✅** — `orchestration.record_governance` emits reviewer/challenger
>   verdicts; knowledge `hits` + gate content-counts carried in metadata; quality
>   analytics derive automatically. Verified end-to-end by the pilot **replay**
>   (`scripts/replay_pilots.py`, `docs/observability/samples/`).
> - **Phase 3 ⛔ skipped by design** — instead of a prompt footer, the orchestrator
>   captures `confidence`/`frameworks_used` from the agent's **existing** output, so
>   no agent `.md` is modified. The footer convention remains optional.
> - **Phase 4 ⏳ future** — OTLP exporter `Sink`, dashboard stand-up, retention job.

---

## Phase 0 — Telemetry library ✅ (this sprint)

Built + tested (`packages/telemetry/`, 23 tests, 96% coverage, ruff/black/mypy clean):
- Canonical `TelemetryEvent` schema + enums + `to_otlp()`.
- Sinks: `JSONLSink` (append-only), `MemorySink`, `NullSink`, `MultiSink`.
- `Recorder`: `emit` + `span`, sampling, redaction.
- Analytics: `engagement_analytics`, `quality_analytics`, `summarize_confidence`.
- Docs: architecture, schema, analytics, dashboards, API contracts, retention/privacy.

**Exit:** library is importable and covered; no call sites yet (zero behavior change).

## Phase 1 — Orchestrator spans (component emit)

Wrap each phase dispatch in the `solve-case` orchestrator with `recorder.span(...)`.
- Gives durations, status, retry/rework for every agent — no `.md` change.
- Add one direct `emit` in `orchestration.report_gate` for the `VALIDATION_GATE`
  event (`validation_status` + state counts in `metadata`).
- Config: `Recorder(JSONLSink())` by default; `NullSink` disables.

**Exit:** every engagement writes `telemetry/<id>.jsonl`; Engineering + Operations
dashboards populate. **Risk:** low (additive; failure-isolated).

## Phase 2 — Governance & knowledge signals

Emit verdicts and hits so the Research dashboard lights up:
- Reviewer/Challenger dispatch spans set `metadata.verdict`.
- `knowledge.retrieve` result → `KNOWLEDGE` event with `metadata.hits`.
- Report gate emits `assumption_count` / `evidence_count` / `unsupported_finding_count`
  from `EngagementState`.

**Exit:** reviewer pass rate, challenger intervention, rework frequency, evidence-vs-
assumption are live. **Risk:** low.

## Phase 3 — Agent telemetry footers

Adopt the fenced `telemetry` footer convention ([API-Contracts §5](API-Contracts.md))
so specialists report `confidence` / `frameworks_used` / `tokens`. Orchestrator
parses the footer into `span.set(...)`.
- Prompt change is a **format addition**, not a logic/consulting change — stays
  within "do not redesign agents" (surface, not behavior). Requires explicit
  sign-off since it touches agent `.md` files.

**Exit:** confidence distribution, framework usage, per-agent token cost are live.
**Risk:** medium (touches prompt surface; footer may be omitted → fields null).

## Phase 4 — Export & dashboards

- Implement an OTLP/HTTP exporter `Sink` (uses `event.to_otlp()`); wire via
  `MultiSink([JSONLSink(), OTLPExporter(...)])`.
- Stand up the four dashboards (Engineering/Product/Research/Operations) reading
  aggregates.
- Add the aggregate-then-prune retention job ([Retention-Privacy §2](Retention-Privacy.md)).
- Status-aware sampler: sample the happy path, keep all failures/blocks.

**Exit:** full observability in production backend; retention + sampling enforced.
**Risk:** medium (new exporter + infra; no app logic).

---

## Sequencing & dependencies

```
Phase 0 (done) ─► Phase 1 (orchestrator spans + gate) ─► Phase 2 (governance/knowledge)
                                    └─► Phase 3 (agent footers, sign-off) ─► Phase 4 (export + dashboards)
```

Phases 1–2 deliver most of the spec (durations, failures, rework, validation, pass
rates) **without touching a single agent prompt**. Phase 3 (the only prompt-surface
change) is isolated and optional — the system is meaningfully observable after
Phase 2.

## Non-goals (unchanged from the brief)

No architecture redesign, no agent redesign, no consulting-logic change. Telemetry
is additive and can be disabled (`NullSink`) with zero behavioral effect.
