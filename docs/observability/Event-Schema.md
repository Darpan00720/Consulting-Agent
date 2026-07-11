# StratAgent Observability — Canonical Event Schema

One event type: **`TelemetryEvent`** ([events.py](../../packages/telemetry/events.py)).
Frozen, `extra="forbid"`, JSON-serializable, schema-versioned.

---

## 1. Fields

| Field | Type | Req | Meaning |
|---|---|:--:|---|
| `event_id` | str | auto | Unique id (also the OTel span id) |
| `schema_version` | int | auto | Telemetry schema version (currently `1`) |
| `timestamp` | datetime (UTC) | auto | When the event was recorded |
| `engagement_id` | str | ✓ | Correlates to the domain log + all engagement telemetry |
| `agent_name` | str | ✓ | Emitting agent/component (e.g. `financial-analyst`, `report_gate`) |
| `phase` | `Phase` | ✓ | Engagement phase (enum below) |
| `status` | `EventStatus` | ✓ | Lifecycle: started/finished/failed/retried/reworked/skipped |
| `duration_ms` | float\|null | | Set on terminal events (finished/failed) |
| `retry_count` | int | | Retries so far for this unit (default 0) |
| `confidence` | float\|null | | Agent-reported confidence [0–1], when known |
| `frameworks_used` | tuple[str] | | Framework note ids used, when reported |
| `tokens` | int\|null | | Token cost, when the host reports it |
| `validation_status` | `ValidationStatus`\|null | | passed/blocked/not_run, for gate events |
| `metadata` | dict | | Bounded, non-sensitive key-values (see redaction) |

### Enums
- **`Phase`**: `intake · classify · gap_analysis · planning · framing · issue_tree ·
  knowledge · analysis · evidence_validation · review · challenge · validation_gate ·
  reporting · knowledge_writeback · orchestration`
- **`EventStatus`**: `started · finished · failed · retried · reworked · skipped`
- **`ValidationStatus`**: `passed · blocked · not_run`

### Well-known `metadata` keys (optional; see [API-Contracts](API-Contracts.md))
`verdict` (review/challenge) · `hits` (knowledge) · `issue_tree_size` ·
`recommendation_count` · `assumption_count` · `evidence_count` ·
`unsupported_finding_count`.

---

## 2. JSON example (one line of a JSONL file)

```json
{
  "event_id": "evt_9f2a...",
  "schema_version": 1,
  "timestamp": "2026-07-10T18:22:04.531Z",
  "engagement_id": "eng_northwind_eu",
  "agent_name": "challenger",
  "phase": "challenge",
  "status": "finished",
  "duration_ms": 157318.0,
  "retry_count": 0,
  "confidence": null,
  "frameworks_used": [],
  "tokens": 30341,
  "validation_status": null,
  "metadata": {"verdict": "stands_with_caveats"}
}
```

## 3. OpenTelemetry mapping (`to_otlp()`)

```json
{
  "name": "challenger:challenge",
  "trace_id": "eng_northwind_eu",
  "span_id": "evt_9f2a...",
  "start_time_unix_nano": 1783701724531000000,
  "end_time_unix_nano": 1783701881849000000,
  "attributes": {
    "stratagent.phase": "challenge",
    "stratagent.status": "finished",
    "stratagent.retry_count": 0,
    "stratagent.tokens": 30341,
    "stratagent.meta.verdict": "stands_with_caveats"
  },
  "status": {"code": "OK"}
}
```

`engagement_id → trace_id` groups every event of one engagement into a single
trace; each event is a span. `status.code` is `ERROR` when `status == failed`,
else `OK`.

## 4. Versioning

`schema_version` is stamped on every event. Additive changes (new optional field,
new enum value) do **not** bump it. A breaking change bumps the constant
`TELEMETRY_SCHEMA_VERSION`; readers branch on it. Old JSONL remains readable
because unknown-but-optional fields are tolerated on read within a major version.
