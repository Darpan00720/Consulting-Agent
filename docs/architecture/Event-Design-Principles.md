---
title: Event Design Principles
status: Stable (invariant)
governing_adr: ADR-002 §Event Model
relates: docs/api/Events.md
date: 2026-06-30
tags: [architecture, events, principles, invariants]
---

# Event Design Principles

Invariant principles every StratAgent event must satisfy — now and for every event
added in the future. These are non-negotiable: an event that violates any of them is
invalid. The concrete contract lives in `docs/api/Events.md`.

## 1. Facts, not commands
An event records something that **has happened** (past tense). It never expresses
intent or a request to act. No `Create…`/`Do…`/`Should…` events.

## 2. Immutable
Events are frozen. Once created, no field may change. **Corrections are new
(compensating) events** — never edits or deletes of an existing event.

## 3. Self-contained
An event must be understandable **in isolation, without reading the current
Engagement State**. Creation events embed the created object; mutation/compensation
events carry the target's typed id **plus** a self-describing snapshot (statement,
claim, …) **and** the reason.

## 4. Explicitly versioned
Every event carries a `schema_version`. Payloads evolve additively; a
non-backward-compatible change requires a new `schema_version` (and usually a new
event type).

## 5. Referenced by strongly-typed, immutable id
Events reference domain objects by their **strongly-typed id** (`EvidenceId`, …),
**never by list position or order**. Ids are immutable.

## 6. Enveloped by `EventMetadata`
Every event carries the reusable envelope: `event_id`, `engagement_id`, `seq`,
`occurred_at`, `recorded_at`, `actor`, `source`, `schema_version`, `causation_id`,
`correlation_id`.

## 7. Actor is distinct from source
`actor` = **who** performed the action; `source` = **how** the event entered the
system. Never conflate them.

## 8. Business time is distinct from system time
`occurred_at` (when the fact happened) is separate from `recorded_at` (when it was
logged). Never collapse them into a single timestamp.

## 9. Exactly one category
Every event belongs to **exactly one** `EventCategory` (via `EVENT_CATEGORIES`).
No event is uncategorized or multi-category.

## 10. Public and stable
Events are public API. They evolve **additively** (new event types, new optional
payload fields, new enum values). Removing/renaming an event type or a required
payload field is breaking and requires an ADR-002 amendment.

## 11. The log is the source of truth; state is a projection
The ordered event log is authoritative. The Engagement State is **derived** by
folding events (projection). State is never the primary record, and projection never
mutates the log.
