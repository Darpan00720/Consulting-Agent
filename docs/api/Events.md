---
title: Engagement Events — Public API Reference
status: Draft (for review — M1.4, pre-implementation)
governing_adr: ADR-002 §Event Model
relates: docs/api/EngagementState.md
tags: [api, events, event-sourcing, reference]
---

# Engagement Events — Public API Reference

The public contract for Engagement State **events**. Events are the system of
record; the Engagement State is their projection (applied in M1.5, not here). This
document defines the event envelope, identifiers, categories, and the full catalog.
It is presented for review **before implementation** (doc-first).

## Principles (contract-level)
1. **Facts, never commands.** Every event names something that *happened*
   (past tense) and describes it. There are no imperative/"do-this" events.
2. **Immutable.** Every event is frozen; it cannot be mutated after creation.
3. **Explicit schema version.** Every event carries `schema_version`.
4. **Self-contained — understandable in isolation.** An event can be understood
   **without reading the current Engagement State**: creation events embed the
   created object; mutation/compensation events carry the target id **plus** a
   self-describing snapshot (e.g., the affected statement/claim) and the reason.
5. **References by immutable, strongly-typed id** — never by list position.
6. **Public API.** Events are part of the public surface and inherit the Stable
   stability guarantees (see `EngagementState.md`); they evolve additively, gated
   by `schema_version`.

## Strongly-typed identifiers
Distinct value objects (Python `NewType` over `str`): same runtime representation,
but not interchangeable at type-check time. Home: `state.identifiers` (re-exported
via the public surface). The generic `Identifier`/`Reference` remain for the
already-Stable domain models; these typed ids are used by **event references**.

| Id | References |
|---|---|
| `EventId` | an event (also `causation_id`) |
| `EngagementId` | the engagement |
| `AssumptionId` | an `Assumption` |
| `EvidenceId` | an `Evidence` record |
| `GapId` | an information `Gap` |
| `IssueNodeId` | an `IssueNode` |
| `FrameworkId` | a `FrameworkSelection` |
| `DeliverableId` | a `Deliverable` |
| `RecommendationId` | the `Recommendations` object |

> Note: the Stable domain models keep `Identifier` for their own `id` (changing
> them is a Stable-API change, out of M1.4 scope). Harmonizing domain-model ids with
> these typed ids is a candidate future step (would require an ADR-002 amendment).

## `EventSource` (how the event entered the system)
`cli · api · agent · system · import · other` — distinct from **actor** (who).

## `EventCategory` (every event belongs to exactly one)
`intake · classification · assumption · planning · knowledge · evidence · analysis ·
governance · recommendation · delivery · hitl · lifecycle · curation`.
A total mapping `EVENT_CATEGORIES: {EventType → EventCategory}` assigns each event
exactly one category (enforced by a completeness test).

## `EventMetadata` (reusable envelope — on every event)
| Field | Type | Notes |
|---|---|---|
| `event_id` | `EventId` | immutable, auto |
| `engagement_id` | `EngagementId` | owning engagement |
| `seq` | `int` | total-order position; **allocated in M1.7** (field only here) |
| `occurred_at` | `datetime` | **business time** — when the fact happened |
| `recorded_at` | `datetime` | **system time** — when it entered the log (default: now) |
| `actor` | `str` | **who** performed the action (human / system / agent-name; enum in M3) |
| `source` | `EventSource` | **how** it entered the system |
| `schema_version` | `int` | per-event schema generation |
| `causation_id` | `EventId \| None` | the event that caused this |
| `correlation_id` | `str \| None` | groups events of one phase |

## Event model shape
Each event = `type` (a `Literal` discriminator) + `metadata: EventMetadata` +
self-contained payload fields. All events are **frozen**. The full set is a
**discriminated union** `Event` keyed on `type`, so JSON round-trips to the correct
concrete event. `category` is derived from `type` via `EVENT_CATEGORIES` (not stored
per instance).

## Event catalog (payload sketches)
Legend: *embed* = carries the full domain object (self-contained); mutation events
carry a typed id **+** a self-describing snapshot + reason.

**intake**
- `EngagementCreated` — `{slug, tenant_id: EngagementId?, created_by}`
- `ProblemDefined` — `{raw_input, real_question?}`
- `ProblemUpdated` — `{real_question, reason?}`
- `ObjectivesRecorded` — `{objectives: [Objective], success_criteria: [str]}` *(embed)*
- `ConstraintsRecorded` — `{constraints: [Constraint]}` *(embed)*
- `StakeholdersRecorded` — `{stakeholders: [Stakeholder]}` *(embed)*

**classification**
- `CaseClassified` — `{classification: CaseClassification}` *(embed)*
- `CaseReclassified` — `{classification: CaseClassification, reason}` *(embed + reason)*
- `InformationGapIdentified` — `{gap: Gap}` *(embed)*
- `GapAnswered` — `{gap_id: GapId, question, resolution}`
- `GapAssumed` — `{gap_id: GapId, question, assumption_id: AssumptionId}`

**assumption**
- `AssumptionAdded` — `{assumption: Assumption}` *(embed)*
- `AssumptionUpdated` — `{assumption_id: AssumptionId, statement, value, rationale?}`
- `AssumptionInvalidated` — `{assumption_id: AssumptionId, statement, reason}`

**planning**
- `EngagementPlanCreated` — `{plan: EngagementPlan}` *(embed)*
- `EngagementReplanned` — `{plan: EngagementPlan, reason}`
- `FrameworkSelected` — `{framework: FrameworkSelection}` *(embed)*
- `FrameworkDeselected` — `{framework_id: FrameworkId, name, reason}`
- `IssueTreeGenerated` — `{nodes: [IssueNode]}` *(embed)*
- `IssueTreeNodeUpdated` — `{node_id: IssueNodeId, question, status, answer?}`

**knowledge**
- `KnowledgeRetrieved` — `{references: [KnowledgeReference]}` *(embed)*

**evidence**
- `EvidenceAdded` — `{evidence: Evidence}` *(embed)*
- `EvidenceValidated` — `{evidence_id: EvidenceId, claim, validator}`
- `EvidenceRejected` — `{evidence_id: EvidenceId, claim, reason}`
- `EvidenceMarkedStale` — `{evidence_id: EvidenceId, claim, as_of?, reason}`

**analysis**
- `SpecialistAnalysisStarted` — `{analysis, owner, node_refs: [IssueNodeId]}`
- `FindingRecorded` — `{analysis, finding: Finding}` *(embed)*
- `SpecialistAnalysisCompleted` — `{analysis, status, finding_count}`

**governance**
- `ReviewerReviewed` — `{notes: ReviewerNotes}` *(embed)*
- `ReviewerApproved` — `{summary}`
- `ReviewerRejected` — `{summary, issues: [str]}`
- `ChallengeRecorded` — `{notes: ChallengeNotes}` *(embed)*
- `ChallengerCleared` — `{summary, caveats: [str]}`
- `ChallengerRejected` — `{summary, counter_case}`

**recommendation**
- `RecommendationDrafted` — `{recommendation: Recommendations}` *(embed)*
- `ConfidenceScored` — `{report: ConfidenceReport}` *(embed)*
- `RecommendationAccepted` — `{recommendation_id: RecommendationId, decision, accepted_by}`

**delivery**
- `ReportGenerated` — `{deliverable: Deliverable}` *(embed)*
- `DeckGenerated` — `{deliverable: Deliverable}` *(embed)*
- `ModelGenerated` — `{deliverable: Deliverable}` *(embed)*

**hitl**
- `HumanInputRequested` — `{prompt, target}`
- `HumanInputProvided` — `{prompt, response, provided_by}`

**lifecycle**
- `PhaseTransitioned` — `{from_status: LifecycleStatus, to_status: LifecycleStatus}`
- `EngagementCompleted` — `{summary}`
- `EngagementFailed` — `{reason}`
- `EngagementAborted` — `{reason, aborted_by}`

**curation**
- `LessonCaptured` — `{lesson, applies_to?}`
- `KnowledgeGraphLinked` — `{graph_node, relationship}`
- `ProfileUpdated` — `{company, summary}`

## Stability
Events are public API and **Stable** once implemented: additive evolution only
(new event types, new optional payload fields); `schema_version` guards payload
changes; the generated JSON schema is drift-tested. Removing or renaming an event
type or required payload field is breaking and requires an ADR-002 amendment.

## Out of scope for M1.4 (defined here, built later)
Applying events to produce state (**projection**, M1.5); `seq` allocation +
optimistic concurrency (M1.7); persistence (M1.8); replay (M1.9). This document
and M1.4 deliver the event **types**, envelope, identifiers, categories, and their
documentation only.
