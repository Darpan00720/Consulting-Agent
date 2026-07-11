# StratAgent Observability — API Contracts & Examples

The public API (`from telemetry import …`) and the integration conventions. All
signatures below are implemented in `packages/telemetry/`.

---

## 1. Recorder (emission)

```python
Recorder(
    sink: Sink | None = None,          # default MemorySink
    *,
    sample_rate: float = 1.0,          # [0.0, 1.0]
    sampler: Callable[[], float] = random,
    redactor: Callable[[Mapping], dict] = default_redactor,
    clock: Callable[[], float] = perf_counter,
)

recorder.emit(*, engagement_id, agent_name, phase, status,
              duration_ms=None, confidence=None, frameworks_used=(),
              tokens=None, retry_count=0, validation_status=None,
              metadata=None) -> TelemetryEvent | None   # None if sampled out

with recorder.span(*, engagement_id, agent_name, phase,
                   emit_start=True) as span:            # SpanHandle
    span.set(confidence=…, frameworks_used=[…], tokens=…,
             validation_status=…, retry_count=…, **metadata)
# emits STARTED on entry, FINISHED (or FAILED on exception) with duration_ms
```

## 2. Sink (destination) — Protocol

```python
class Sink(Protocol):
    def emit(self, event: TelemetryEvent) -> None: ...
    def close(self) -> None: ...
```
Ships: `JSONLSink(root="telemetry")` (append-only, `.read(id)` / `.read_all()`),
`MemorySink` (`.events`), `NullSink`, `MultiSink([...])`. A custom exporter (OTLP,
HTTP, DB) just implements this Protocol.

## 3. Analytics (read)

```python
engagement_analytics(events: Iterable[TelemetryEvent]) -> EngagementAnalytics
quality_analytics(events: Iterable[TelemetryEvent]) -> QualityAnalytics
summarize_confidence(values: Iterable[float]) -> ConfidenceSummary
```

## 4. Metadata key contract

Emitters populate these keys so analytics can read them (all optional):

| Key | Emitted by | Type | Used for |
|---|---|---|---|
| `verdict` | reviewer / challenger event | str | pass rate, intervention, rework |
| `hits` | knowledge event | int | retrieval effectiveness |
| `issue_tree_size` | issue-tree / gate event | int | tree-size metric |
| `recommendation_count` | report / gate event | int | rec count |
| `assumption_count` | gate event | int | assumption total |
| `evidence_count` | gate event | int | evidence total |
| `unsupported_finding_count` | gate event | int | unsupported findings |

## 5. Agent telemetry footer (convention)

Specialists append a fenced block the orchestrator parses (adds no consulting
logic). Absent footer → those fields stay null.

````markdown
```telemetry
confidence: 0.55
frameworks_used: [market-attractiveness-right-to-win, build-buy-partner]
tokens: 26940
```
````

---

## 6. Examples

### 6a. Orchestrator times a phase (design pattern)
```python
from telemetry import Recorder, JSONLSink, Phase

rec = Recorder(JSONLSink())            # writes telemetry/<engagement_id>.jsonl

with rec.span(engagement_id=eid, agent_name="market-analyst",
              phase=Phase.ANALYSIS) as span:
    result = dispatch_market_analyst(...)         # the real subagent call
    footer = parse_telemetry_footer(result)       # confidence, frameworks, tokens
    span.set(**footer)
# → STARTED + FINISHED(duration_ms, confidence, frameworks_used, tokens)
```

### 6b. Report gate emits a validation event (component emit)
```python
from telemetry import Phase, EventStatus, ValidationStatus

gate = run_report_gate(state)          # orchestration.report_gate
rec.emit(
    engagement_id=state.metadata.engagement_id,
    agent_name="report_gate",
    phase=Phase.VALIDATION_GATE,
    status=EventStatus.FINISHED,
    validation_status=ValidationStatus.PASSED if gate.ok else ValidationStatus.BLOCKED,
    metadata={
        "issue_tree_size": len(state.issue_tree),
        "assumption_count": len(state.assumptions),
        "evidence_count": len(state.evidence),
    },
)
```

### 6c. Read analytics for a dashboard
```python
from telemetry import JSONLSink, engagement_analytics, quality_analytics

sink = JSONLSink()
one = engagement_analytics(sink.read("eng_northwind_eu"))
print(one.duration_by_phase_ms, one.confidence.buckets)

allq = quality_analytics(sink.read_all())
print(allq.reviewer_pass_rate, allq.challenger_intervention_rate)
```

### 6d. Fan-out to files + a future OTLP exporter
```python
from telemetry import Recorder, JSONLSink, MultiSink
# OTLPExporter implements Sink.emit via event.to_otlp(); not shipped here.
rec = Recorder(MultiSink([JSONLSink(), OTLPExporter(endpoint="...")]))
```

---

## 7. Integration API (v1.0 — the live-path wiring)

### 7a. `EngagementTracer` (`telemetry`)
Per-engagement facade the orchestrator and CLI share. Binds one `engagement_id`;
keeps an in-memory mirror so `analytics()` works regardless of the durable sink.

```python
from telemetry import EngagementTracer, Phase

tracer = EngagementTracer(engagement_id, root="telemetry")   # JSONLSink under the hood
with tracer.agent("financial-analyst", Phase.ANALYSIS) as span:
    result = dispatch(...)
    span.set(confidence=0.5, frameworks_used=["profit-tree"], tokens=12596)
tracer.rework(agent_name="financial-analyst", phase=Phase.ANALYSIS)   # governance loop
tracer.phase_marker(phase=Phase.REPORTING)                            # orchestration marker
summary = tracer.analytics()                                          # EngagementAnalytics
```

### 7b. Orchestration bridge (`orchestration`)
Python emission for the code components (gate + governance), deriving content
counts from `EngagementState`.

```python
from orchestration import instrument_gate, record_gate, record_governance, content_metadata

result = instrument_gate(tracer, state)     # runs the report gate AND records the event
record_governance(tracer, state)            # emits REVIEW + CHALLENGE verdict events
meta = content_metadata(state)              # issue_tree_size, assumption_count, verdicts, …
```

### 7c. CLIs (for the markdown/LLM orchestrator, via Bash)
```
# append one span
uv run python scripts/record_telemetry.py --engagement <id> --agent <name> \
  --phase <phase> --status finished --duration-ms <ms> [--confidence c] \
  [--frameworks a,b] [--tokens n] [--meta verdict=approved]

# summarize / export
uv run python scripts/engagement_telemetry.py --engagement <id>          # engagement analytics
uv run python scripts/engagement_telemetry.py --all --quality            # quality analytics
uv run python scripts/engagement_telemetry.py --engagement <id> --otlp   # OTLP spans

# replay the pilots into sample traces + verify
uv run python scripts/replay_pilots.py
```
