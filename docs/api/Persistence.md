---
title: Persistence — Public API Reference
status: Stable
lifecycle_entered: 2026-07-04 (M1.8 completion)
governing_adr: ADR-002 (Engagement State); M1.8-Design (DD-1..DD-7 + PER-001..011)
applies_to: packages/persistence
tags: [api, persistence, save, load, reference]
---

# Persistence — Public API Reference

Durable, file-backed storage for engagements. `persistence` is the **only**
IO-touching package in the domain; `state` stays completely IO-free (DD-1).
This document is the public contract for `persistence`; anything not listed
here is internal and may change without notice.

## Access & entry point
- The public surface is exactly seven names (frozen; see
  `tests/persistence/test_api_freeze.py`):
  `EngagementStore` and the error taxonomy `PersistenceError`,
  `PersistenceErrorCode`, `MissingArtifactError`, `TornWriteError`,
  `CorruptArtifactError`, `IncompatibleVersionError`.
- **`EngagementStore` is the sole entry point.** `save`/`load` are its methods;
  there are **no** module-level IO functions. The implementation modules
  (`paths`, `format`, `atomic`, and the store internals) are private.
- Persisted artifacts live under `engagements/<slug>/` and are gitignored
  (runtime output; DD-4).

## `EngagementStore`
| Member | Signature | Contract |
|---|---|---|
| constructor | `EngagementStore(root: Path)` | Binds a store to a root directory. No IO on construction. |
| `save` | `save(engagement: Engagement) -> None` | Atomically persist the engagement. Manifest is written last as the commit marker. |
| `load` | `load(slug: str) -> Engagement` | Reconstruct a verified, **append-capable** engagement, or raise a typed error. |

### On-disk layout (`engagements/<slug>/`)
| File | Format | Role |
|---|---|---|
| `events.log` | NDJSON, one `Event` per line, contiguous seq order | The source of truth (append-only). |
| `state.json` | JSON `EngagementState` | The **canonical projected snapshot** (see below). |
| `manifest.json` | JSON `{format_version, log_sha256, snapshot_sha256}` | The commit marker + integrity checksums. No timestamps/UUIDs/paths/machine metadata. |

### Save workflow (fixed order)
1. Read the committed log (via the approved `_pipeline` seam, P-DD-A).
2. Build the canonical snapshot `project(log)`.
3. Compute SHA-256 over the serialized log and snapshot.
4. Atomic-write `events.log`.
5. Atomic-write `state.json`.
6. Atomic-write `manifest.json` — **always last**.

Because the manifest (with matching checksums) is written last, a crash before
it leaves the set detectably incomplete — never "partially persisted"
(PER-012). Each write is atomic: temp file → flush → `fsync` → `os.replace` →
directory `fsync` (PER-005).

### Load workflow (fixed order)
1. Read `manifest.json` (absent → `MissingArtifactError`; present-but-partial
   set → `TornWriteError`).
2. Read `state.json` and `events.log`.
3. Verify SHA-256 against the manifest.
4. Decode the snapshot and log.
5. `verify_log(log)` — replay integrity of the log.
6. `verify_pair(log, snapshot)` — the log/snapshot agreement gate.
7. `AppendPipeline(snapshot, log=…, append_supported=True)` → return
   `Engagement`.

Load **never** repairs, renumbers, migrates, or re-projects (PER-008). Recovery
of stale/torn artifacts is out of scope for M1.8 — it is M1.9 (DD-5/DD-6).

## Canonical persistence representation

> **Persistence stores canonical projected snapshots rather than runtime
> incremental state.**

The runtime `EngagementState` carried by a live engagement is built
*incrementally*: `Engagement.create()` constructs the state directly (leaving
`projection_version == 0`), and each `apply()` stamps only `state_version`,
inheriting `projection_version` unchanged. So a live snapshot carries stale
projection provenance (`projection_version == 0`), even though its domain
content is correct.

`save()` therefore does **not** persist the runtime `committed.state`. It
persists `project(log)` — the state re-derived by folding the log through the
current projection engine — whose `projection_version == PROJECTION_VERSION`.
The event log, domain state, version, and append capability are preserved
exactly; only the projection *provenance* is normalized. We call this
**canonical engagement semantics**.

### Why `verify_pair()` always succeeds for persisted artifacts
`verify_pair(log, snapshot)` (M1.7.4, rule R14) requires
`snapshot.projection_version == PROJECTION_VERSION`; a snapshot at a lower
version is rejected as `projection_stale`. Since `save()` always writes
`project(log)`, every persisted `(log, snapshot)` pair carries the current
`PROJECTION_VERSION` by construction and therefore **always** passes
`verify_pair` on load — with no replay, no repair, and no re-projection at load
time. `verify_pair` itself is **frozen and unchanged**; the normalization
happens entirely on the persistence side. This is the canonical persistence
representation, not a workaround. It is permanently pinned by
`test_store.py::test_s4_16_projection_provenance_normalized_on_persist` and
`test_integration.py::test_persisted_snapshot_is_canonical_projection`.

A corollary: a save/load round-trip normalizes `projection_version` `0 → 2` on
the first cycle; all subsequent cycles are byte-identical (PER-011). Consumers
comparing engagement state across a persistence boundary must treat
`projection_version` as normalized provenance, not payload.

## Error taxonomy
All persistence errors inherit `PersistenceError` (itself a `StratAgentError`)
and carry a stable `PersistenceErrorCode`. Raw `OSError` is never leaked outside
`EngagementStore`; unexpected OS/decoding failures are wrapped, preserving
`__cause__`.

| Error | Code | Raised when |
|---|---|---|
| `MissingArtifactError` | `missing_artifact` | Nothing persisted at the slug (no manifest, no payload). |
| `TornWriteError` | `torn_write` | A partial set — manifest missing but payload present, or manifest present but a referenced file missing. |
| `CorruptArtifactError` | `corrupt_artifact` | Checksum mismatch, or malformed JSON/NDJSON, or an unexpected read/decode failure. |
| `IncompatibleVersionError` | `incompatible_version` | Unsupported `format_version` in the manifest. |

## Stability guarantees
- The seven public names and `EngagementStore`'s method signatures are frozen
  (`test_api_freeze.py`).
- `PersistenceErrorCode` is a closed set of four stable string values
  (`test_contracts.py`).
- The manifest schema is fixed (three fields, no non-deterministic data), which
  is what makes persistence deterministic (PER-011).
- `packages/state` remains IO-free; persistence depends on it, never the
  reverse (PER-009, DD-1).

See also: [Engagement State API](EngagementState.md),
[Performance Baselines](../performance/baselines.md),
[projection versioning](../architecture/projection-versioning.md),
[M1.8 Completion Report](../reviews/M1.8-Completion-Report.md).
