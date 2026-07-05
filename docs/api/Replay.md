---
title: Replay — Public API Reference
status: Stable
lifecycle_entered: 2026-07-05 (M1.9 completion)
governing_adr: ADR-001, ADR-002 (no ADR modified by M1.9)
applies_to: packages/replay
tags: [api, replay, recovery, reference]
---

# Replay — Public API Reference

Rebuild engagements from their event logs. `replay` is **pure orchestration
over frozen seams** — it verifies a log, folds it through the projection engine,
verifies the `(log, snapshot)` pair, and reconstructs an append-capable
`Engagement`. It re-implements none of those steps, mutates no input, writes no
persistence, and changes no global state (RP-016). It is a **sibling** of
`state` and `persistence` and depends on both; neither depends on it.

## Access & entry point
- The public surface is exactly six names (frozen; see
  `tests/replay/test_api_freeze.py`): `ReplayEngine`, `ReplayContract`, `replay`,
  `recover`, `ReplayError`, `ReplayIntegrityError`.
- `ReplayEngine` is the entry point; `replay`/`recover` are also exposed as
  module-level convenience functions that delegate to a default engine.
- The implementation modules (`engine`, `contracts`, `errors`) are otherwise
  internal.

## `ReplayEngine`
A frozen, field-less, stateless value (RP-016) — reusable and immutable.

| Member | Signature | Contract |
|---|---|---|
| `replay` | `replay(log: Sequence[Event]) -> Engagement` | Rebuild an append-capable engagement from a committed event log. |
| `recover` | `recover(log: Sequence[Event], snapshot: EngagementState) -> Engagement` | Rebuild from a persisted `(log, snapshot)` pair, upgrading a stale snapshot. |

Module-level `replay(log)` and `recover(log, snapshot)` are equivalent to
`ReplayEngine().replay(...)` / `.recover(...)`.

## `ReplayContract`
A `runtime_checkable` `Protocol` describing the replay capability
(`replay(self, log) -> Engagement`). `ReplayEngine` conforms structurally.
Implementations must be observationally pure (RP-016).

## Errors
| Type | Role |
|---|---|
| `ReplayError` | Additive base for replay **orchestration** failures (`StratAgentError`). Introduces **no** machine codes and does not touch the frozen replay-integrity taxonomy. |
| `ReplayIntegrityError` | Re-exported **unchanged** from `state.append` (M1.7.4, frozen). At-rest integrity defects (bad log, stale/future/foreign snapshot) surface as this error; replay raises the frozen object itself, never a redefinition. |

## Canonical replay pipeline
`replay(log)` runs a single fixed pipeline — no alternate, fast, or partial path:

```
verify_log(log)                       # at-rest integrity gate (M1.7.4); fatal on any defect
    -> state = project(log)           # canonical fold (M1.5/M1.7.2); pv == PROJECTION_VERSION
    -> verify_pair(log, state)        # (log, snapshot) agreement gate (M1.7.4)
    -> AppendPipeline(state, log=log, append_supported=True)   # make_committed runs inside (P23)
    -> Engagement(pipeline)
```

Because `project(log)` always carries the current `PROJECTION_VERSION`, a log
that passes `verify_log` also passes `verify_pair`; replay of a verified log
cannot fail at the fold or pair step. Integrity is never bypassed (RP-017).

## Recovery pipeline
`recover(log, snapshot)` operates on a **decoded persisted pair** (not a store
handle — `EngagementStore.load` itself rejects a stale snapshot):

```
verify_log(log)                       # fatal log defects propagate (RP-022)
verify_pair(log, snapshot)
  ├─ passes            -> Engagement(AppendPipeline(snapshot, log=log, append_supported=True))
  └─ PROJECTION_STALE  -> project(log)               # discard snapshot; exactly one re-projection (RP-021)
                          verify_pair(log, projected)
                          Engagement(AppendPipeline(projected, log=log, append_supported=True))
```

Recovery is attempted **only** for `PROJECTION_STALE` (RP-018). Every other
`ReplayIntegrityError` — `PROJECTION_FUTURE`, `STATE_VERSION_MISMATCH`,
`ENGAGEMENT_MISMATCH`, and all log defects — propagates **unchanged** (RP-022).

## Replay guarantees
- **Single reconstruction path** through the frozen seams; no logic duplicated
  (RP-001, RP-002).
- **Deterministic** — `replay(log)` is a pure function of `log`; equal logs give
  equal engagements (RP-003, RP-024, RP-025), and repeated replay is a fixpoint
  (RP-005).
- **Fold-equivalent** — `replay(log).get_state() == project(log)` (RP-004,
  RP-026).
- **No fabrication/repair** — the committed log equals the input log; nothing is
  renumbered, dropped, synthesized, or reordered (RP-011, RP-012).
- **Version triangle preserved** — `version == current_version(log) ==
  state.metadata.state_version` (RP-013, RP-028).
- **Integrity unbypassable** — a verify failure aborts with no `Engagement`
  (RP-006, RP-017).

## Recovery guarantees
- **Upgrade = whole-log re-projection only** — no event-schema migration, no
  upcasting, no log repair (RP-021).
- **Recovered engagement is the canonical projection** — `get_state() ==
  project(log)` with `projection_version == PROJECTION_VERSION` (RP-019).
- **Never writes persistence** — no snapshot mutation, no file rewrite, no
  `EngagementStore.save`; persisting the upgrade is the caller's responsibility
  (RP-020, DD-7).
- **Deterministic** — recovering the same pair twice is identical (RP-023).

## Append-capable output contract
Both `replay` and `recover` return an `Engagement` built with
`append_supported=True`: the next append continues at `current_version(log)`
with a contiguous sequence (RP-010, RP-027). This removes the read-only-adoption
limitation of `Engagement.from_state`/`from_json` for log-backed engagements.

## Projection-version upgrade behaviour
- A persisted snapshot at `projection_version == PROJECTION_VERSION` is used
  as-is (no re-projection).
- A snapshot **below** the current version (`PROJECTION_STALE`) is discarded and
  the verified log is re-projected under the current implementation — the
  authoritative upgrade path deferred from M1.8 (DD-6).
- A snapshot **above** the current version (`PROJECTION_FUTURE`) is **fatal** —
  it requires a newer binary, not recovery (never down-projected).

See also: [Engagement State API](EngagementState.md),
[Persistence API](Persistence.md),
[Replay layer (architecture)](../architecture/replay-layer.md),
[Performance Baselines](../performance/baselines.md),
[M1.9 Completion Report](../reviews/M1.9-Completion-Report.md).
