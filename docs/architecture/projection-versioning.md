---
title: Projection Versioning Policy (projection_version)
status: Stable policy
date: 2026-06-30
relates: [packages/state/projection.py, docs/api/EngagementState.md]
tags: [architecture, projection, versioning]
---

# Projection Versioning Policy

`EngagementState.projection_version` records **which projection implementation
produced a state**. `PROJECTION_VERSION` (in `state.projection`) is the current
implementation version; `project()` stamps it onto every state it produces. This
supports replay evolution: a state's `projection_version` identifies the fold logic
that built it, so a future change can be migrated or re-projected deliberately.

## Values
- **`0`** — the state was **not** produced by projection (e.g., constructed directly
  via the `Engagement` facade). This is the default on `EngagementState`.
- **`N` (≥ 1)** — produced by projection implementation version `N`. `project()`
  currently stamps `PROJECTION_VERSION = 2`.

## When it MUST change (bump `PROJECTION_VERSION`)
Bump when a change to the reducer would cause the **same, previously-valid event log
to fold into a different `EngagementState`**. For example:
- Changing how an existing event maps to state (different field or value).
- Changing compensating-event semantics (e.g., how `EvidenceMarkedStale` affects state).
- Changing the seed/initial state or default field population.
- Removing or altering an existing reducer's effect.

Such a change means a stored state (stamped with the old version) and a freshly
re-projected state may differ; the version distinguishes them and signals that replay
migration may be required.

## When it MUST NOT change
Do **not** bump when the projection of every previously-valid log is unchanged:
- Refactoring, renaming internals, or performance optimization that preserves output.
- Adding a reducer for a **new** event type — no pre-existing log could contain that
  event, so no existing log's projection changes.
- Formatting, comments, tests, or documentation.

## Governance
- `PROJECTION_VERSION` is a monotonically increasing integer.
- A bump is a deliberate, reviewed change recorded in `CHANGELOG.md`, and — once
  persistence and replay land (M1.8 / M1.9) — must be accompanied by a migration note
  describing how existing stored states are handled.

## Version history
| Version | Date | Why the projection changed | Migration |
|---|---|---|---|
| 1 | 2026-06-30 | Initial fold (M1.5). | — |
| 2 | 2026-07-02 | **M1.7.2 (design D4):** `apply()` now derives `metadata.state_version` from `event.metadata.seq`, making projection the single authority for `state_version`. The same previously-valid log folds to a different state (states formerly retained the default `state_version = 0`), which is exactly the policy's "MUST bump" case. | No stored states exist pre-release; any state stamped `projection_version = 1` is refreshed by re-projecting its log. |
