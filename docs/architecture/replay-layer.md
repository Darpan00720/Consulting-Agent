---
title: Replay Layer — Architecture Addendum (post-M1.9)
status: Stable addendum to the frozen v1.0 baseline
date: 2026-07-05
supplements: docs/reviews/Architecture-v1.0.md (FROZEN — not modified)
governing_adr: ADR-001, ADR-002 (no ADR modified by M1.9)
evidence-discipline: every claim [Verified] / [Inference] / [Unknown]
---

# Replay Layer — Architecture Addendum

**Architecture v1.0 remains frozen and unmodified** (`docs/reviews/Architecture-v1.0.md`,
`status: FROZEN`, immutable unless a new ADR changes it). That baseline named
replay a *future extension point*; this addendum records that the extension is
now **implemented** by M1.9, without altering the baseline — the same way M1.8
realized the persistence extension point without editing v1.0. [Verified —
v1.0 "Extension Points"; M1.8 completion did not touch the baseline]

## The replay layer (`packages/replay`)

A new **sibling** of `state` and `persistence` [Verified]. It depends on both;
neither depends on it. Like `persistence`, it is **pure orchestration over
frozen seams** and owns no substantive logic:

| Frozen seam | Layer | Replay's use |
|---|---|---|
| `verify_log` / `verify_pair` | L6 `state.append` (integrity, M1.7.4) | calls (at-rest gate) |
| `project` / `apply` | projection (M1.5/M1.7.2) | calls (the fold) |
| `make_committed` / `AppendPipeline` | L6 `state.append` (M1.7.3) | calls (reconstruction; `make_committed` transitive, P23) |
| `EngagementStore` | persistence (M1.8) | reads decoded artifacts; **never** writes during recovery |

Public surface (frozen, 6 names): `ReplayEngine`, `ReplayContract`, `replay`,
`recover`, `ReplayError`, `ReplayIntegrityError`. Full contract: `docs/api/Replay.md`.

## Extension points — updated view

The v1.0 baseline listed these as *future*. Post-M1.9 status:

- **Persistence (M1.8)** — ✅ implemented (`packages/persistence`). Persists
  `CandidateCommit.events` + the `(log, project(log))` pair; restores via
  `verify_pair` → `make_committed`. [Verified]
- **Replay (M1.9)** — ✅ implemented (`packages/replay`). Folds a verified log
  through `project` and constructs an append-capable engagement
  (`append_supported=True`), removing the read-only-adoption restriction for
  log-backed engagements. Property/stress suite (the deferred "S7") landed here.
  [Verified]
- **Snapshots / projection-version policy (M1.9)** — ✅ recovery re-projects a
  `PROJECTION_STALE` snapshot (whole-log re-projection; the M1.8 DD-6 deferral).
  [Verified]
- **Agent Manager (M6), Authorization (M6), Knowledge Graph, Ruflo/MCP** —
  unchanged, still future. [Verified]

## Replay ↔ persistence relationship

The two layers compose but stay strictly separated (DD-1: `state` is IO-free;
persistence is the IO owner; replay is IO-free orchestration) [Verified]:

- **Normal load** — `EngagementStore.load` reads the `(log, snapshot)` pair,
  verifies it, and reconstructs directly (no replay needed) because M1.8 stores
  the canonical `project(log)` snapshot. [Verified]
- **Aged snapshot** — if `PROJECTION_VERSION` advances, an older persisted
  snapshot becomes `PROJECTION_STALE`. `load` refuses it (its `verify_pair`
  raises); the caller decodes the raw artifacts and calls `replay.recover`,
  which discards the stale snapshot and re-projects. [Verified]
- **Write-back is the caller's job** — recovery returns an in-memory
  append-capable engagement; persisting the upgrade is an explicit
  `EngagementStore.save` (DD-7 no-autosave; replay writes nothing). [Verified]

The state lifecycle is therefore complete end to end: **create → append →
validate → persist → load → replay/recover** — all on the frozen v1.0
architecture. [Inference]

## What did not change

No ADR; the 10-method facade surface; projection purity/determinism;
`make_committed` as the sole `Committed` constructor; replay integrity R1–R18;
`packages/state` and `packages/persistence` (zero-diff across M1.9). Any change
to these still requires a new ADR. [Verified]
