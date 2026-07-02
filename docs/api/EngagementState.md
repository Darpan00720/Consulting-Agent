---
title: Engagement State — Public API Reference
status: Stable
lifecycle_entered: 2026-06-30 (following M1.3 approval)
governing_adr: ADR-002
applies_to: packages/state, packages/common (value objects)
tags: [api, engagement-state, reference]
---

# Engagement State — Public API Reference

The public data contract for the Engagement State. This is the reference all future
milestones build against. It documents **only the public surface** — models, value
objects, enums, fields, and stability guarantees. Internal implementation
(validators, and the forthcoming event/projection/persistence machinery) is **not**
part of this contract and may change without notice.

## Access & entry point
- The public surface is the `state` package (models, enums, and — from M1.3 — the
  `Engagement` facade) plus the `common` value objects.
- **From M1.3, the `Engagement` facade is the sole entry point for operations**
  (create, load, validate, serialize; mutation-via-events arrives with the event
  API). The models below are the **data contract** the facade exposes.
- Modules not listed here are private. Do not import them directly.

## Value objects (`common`)
| Value object | Definition | Notes |
|---|---|---|
| `ConfidenceScore` | `float` constrained to `[0.0, 1.0]` | One definition, reused by every confidence field — no duplicated validation |
| `Identifier` | opaque non-empty string — an object's **own** id | Immutable once set |
| `Reference` | string id that **points to** another object's id | Referential integrity enforced later (M1.6) |
| `new_id()` | factory returning a unique `Identifier` | IDs are the stable reference targets — never rely on list order |

## Strongly-typed identifiers
**Controlled API refinement (pre-external-release, 2026-06-30):** addressable domain
objects use distinct typed ids (`NewType` over `str`) for their `id`, aligning the
domain and event models so no conversion code is needed between layers. Same runtime
representation, distinct at type-check; JSON-schema-compatible. Home: `state.identifiers`.

| Typed id | Used by |
|---|---|
| `EngagementId` | `EngagementMetadata.engagement_id` |
| `EvidenceId` | `Evidence.id` |
| `AssumptionId` | `Assumption.id` |
| `GapId` | `Gap.id` |
| `IssueNodeId` | `IssueNode.id` |
| `FrameworkId` | `FrameworkSelection.id` |
| `DeliverableId` | `Deliverable.id` |
| `RecommendationId` | `Recommendations.id` |
| `EventId` | events (see `Events.md`) |

Embedded/nested records never referenced by id keep the base `Identifier`.

## Base: `DomainObject` (inherited by every domain model below)
Every model in this reference (except `EngagementState` and `EngagementMetadata`)
inherits these fields:

| Field | Type | Default | Notes |
|---|---|---|---|
| `id` | `Identifier` | auto (`new_id()`) | **Immutable** — the primary reference target for events, replay, and APIs |
| `created_at` | `datetime \| None` | `None` | Optional audit metadata |
| `updated_at` | `datetime \| None` | `None` | Optional audit metadata |
| `created_by` | `str \| None` | `None` | Optional audit metadata |
| `updated_by` | `str \| None` | `None` | Optional audit metadata |

All models reject unknown fields.

## Root: `EngagementState`
The single source of truth. **Valid with only `metadata`** — every other section
begins `None` or as an empty collection and is populated over the lifecycle.

| Field | Type | Default | ADR-002 |
|---|---|---|---|
| `metadata` | `EngagementMetadata` | — (required) | §1 |
| `status` | `LifecycleStatus` | `intake` | §2 |
| `problem` | `ProblemDefinition \| None` | `None` | §3 |
| `objectives` | `list[Objective]` | `[]` | §4 |
| `success_criteria` | `list[str]` | `[]` | §4 |
| `constraints` | `list[Constraint]` | `[]` | §5 |
| `stakeholders` | `list[Stakeholder]` | `[]` | §6 |
| `classification` | `CaseClassification \| None` | `None` | §7 |
| `information_gaps` | `list[Gap]` | `[]` | §8 |
| `assumptions` | `list[Assumption]` | `[]` | §9 |
| `evidence` | `list[Evidence]` | `[]` | §14 |
| `plan` | `EngagementPlan \| None` | `None` | §10 |
| `frameworks` | `list[FrameworkSelection]` | `[]` | §11 |
| `issue_tree` | `list[IssueNode]` | `[]` | §12 |
| `knowledge_references` | `list[KnowledgeReference]` | `[]` | §13 |
| `financial_analysis` | `AnalysisBlock \| None` | `None` | §15 |
| `market_analysis` | `AnalysisBlock \| None` | `None` | §16 |
| `operations_analysis` | `AnalysisBlock \| None` | `None` | §17 |
| `strategy_analysis` | `AnalysisBlock \| None` | `None` | §18 |
| `risk_analysis` | `AnalysisBlock \| None` | `None` | §19 |
| `reviewer_notes` | `ReviewerNotes \| None` | `None` | §20 |
| `challenge_notes` | `ChallengeNotes \| None` | `None` | §21 |
| `recommendations` | `Recommendations \| None` | `None` | §22 |
| `confidence` | `ConfidenceReport \| None` | `None` | §23 |
| `deliverables` | `list[Deliverable]` | `[]` | §24 |
| `knowledge_links` | `list[KnowledgeLink]` | `[]` | §25 |
| `phase_history` | `list[PhaseRecord]` | `[]` | §2 |
| `quality_gates` | `list[QualityGate]` | `[]` | §2 |
| `pending_requirements` | `list[PendingRequirement]` | `[]` | §2 |
| `projection_version` | `int` | `0` | projection provenance (stamped by `project`) |

### `EngagementMetadata` (§1)
`engagement_id: EngagementId` · `tenant_id: str` · `slug: str` · `created_at: datetime` (auto)
· `updated_at: datetime` (auto) · `created_by: "human" | "system" = "human"` ·
`state_version: int = 0` · `schema_version: int = 1`.

## Ledgers
**`Evidence`** (§14): `claim: str` · `type: EvidenceType` · `source: str?` ·
`method: str?` · `as_of: datetime?` · `confidence: ConfidenceScore` ·
`validated: bool = False` · `validator: str?`.
Required-by-type: `external_source`/`assumption` → `source`; `computed` → `method`.

**`Assumption`** (§9): `statement: str` · `value: str` · `rationale: str` ·
`owner: str` · `confidence: ConfidenceScore` · `load_bearing: bool = False` ·
`breakeven: str?` · `status: AssumptionStatus = active`.
Rule: `load_bearing` → `breakeven` required.

## Section models

**Scoping (§3–§8)**
- **`Document`** (§3): `path: str` · `kind: str?` · `ingested_at: datetime?` · `screened: bool = False`
- **`ProblemDefinition`** (§3): `raw_input: str` · `documents: list[Document] = []` · `real_question: str?` · `restated_at: datetime?`
- **`Objective`** (§4): `statement: str` · `metric: str?` · `target: str?` · `priority: int?` · `source: ObjectiveSource?`
- **`Constraint`** (§5): `statement: str` · `type: ConstraintType = other` · `hard: bool = True`
- **`Stakeholder`** (§6): `name_or_role: str` · `relationship: StakeholderRelationship = other` · `interest: str?`
- **`CaseClassification`** (§7): `primary_archetype: CaseArchetype` · `secondary_archetype: CaseArchetype?` · `confidence: ConfidenceScore` · `rationale: str?`
- **`Gap`** (§8): `question: str` · `criticality: GapCriticality = useful` · `status: GapStatus = open` · `resolution: str?` · `assumption_ref: Reference?`

**Planning (§10–§13)**
- **`PlanStep`** (§10): `description: str` · `agent: str?` · `depends_on: list[Reference] = []` · `status: PlanStepStatus = pending`
- **`EngagementPlan`** (§10): `steps: list[PlanStep] = []` · `parallel_groups: list[list[Reference]] = []` · `replans: int = 0`
- **`FrameworkSelection`** (§11): `name: str` · `archetype: CaseArchetype?` · `rationale: str?` · `adaptation: str?` · `source_ref: Reference?`
- **`IssueNode`** (§12): `parent: Reference?` · `question: str` · `owner: str?` · `status: IssueNodeStatus = open` · `answer: str?` · `confidence: ConfidenceScore?` · `evidence_refs: list[Reference] = []`
- **`KnowledgeReference`** (§13): `kind: KnowledgeRefKind` · `vault_path: str?` · `graph_node: str?` · `query: str?` · `relevance: ConfidenceScore?` · `retrieved_at: datetime?`

**Analysis (§15–§19)**
- **`Finding`**: `question: str` · `answer: str?` · `method: str?` · `evidence_refs: list[Reference] = []` · `assumption_refs: list[Reference] = []` · `confidence: ConfidenceScore?`
- **`SensitivityCase`**: `driver: str` · `base: str?` · `stress: str?` · `effect: str?`
- **`AnalysisBlock`**: `owner: str?` · `node_refs: list[Reference] = []` · `findings: list[Finding] = []` · `sensitivity: list[SensitivityCase] = []` · `status: AnalysisStatus = pending`

**Governance (§20–§21)**
- **`ReviewCheck`** (§20): `name: ReviewCheckName` · `result: CheckResult` · `detail: str?`
- **`ReviewerNotes`** (§20): `checks: list[ReviewCheck] = []` · `verdict: ReviewVerdict?` · `issues: list[str] = []`
- **`ChallengeNotes`** (§21): `loadbearing_test: str?` · `counter_case: str?` · `what_would_change: list[str] = []` · `verdict: ChallengeVerdict?`

**Output (§22–§25)**
- **`NextStep`** (§22): `step: str` · `sequence: int?` · `depends_on: list[Reference] = []`
- **`RejectedAlternative`** (§22): `option: str` · `why_not: str?`
- **`Recommendations`** (§22): `decision: str?` · `rationale: str?` · `next_steps: list[NextStep] = []` · `risks: list[str] = []` · `alternatives_rejected: list[RejectedAlternative] = []` · `status: RecommendationStatus = draft`
- **`ConfidenceReport`** (§23): `by_section: dict[str, ConfidenceScore] = {}` · `overall: ConfidenceScore?` · `method: str?` · `drivers: list[str] = []`
- **`Deliverable`** (§24): `kind: DeliverableKind` · `path: str?` · `format: str?` · `status: DeliverableStatus = pending` · `generated_at: datetime?`
- **`KnowledgeLink`** (§25): `graph_node: str?` · `relationship: str?` · `vault_note: str?` · `tenant_id: str?`

**Lifecycle audit (§2)**
- **`PhaseRecord`**: `phase: LifecycleStatus` · `entered_at: datetime?` · `exited_at: datetime?` · `result: str?`
- **`QualityGate`**: `gate: str` · `result: GateResult` · `by: str?` · `ts: datetime?`
- **`PendingRequirement`** (execution blocker *or* missing information): `kind: PendingKind = other` · `description: str` · `ref: Reference?`

## Public enums
| Enum | Values |
|---|---|
| `LifecycleStatus` | intake · classifying · gap_analysis · planning · framing · issue_tree · knowledge · analysis · evidence_validation · review · challenge · reporting · completed · failed · aborted |
| `EvidenceType` | client_fact · external_source · computed · assumption |
| `AssumptionStatus` | active · invalidated · confirmed |
| `CaseArchetype` | profitability · revenue_growth · cost_reduction · pricing · market_entry · m_and_a · new_product_launch · turnaround · digital_transformation · supply_chain · organizational_design · ai_strategy · corporate_strategy · customer_strategy · sales_marketing · pe_due_diligence · generic · **unknown** |
| `ObjectiveSource` | client_stated · inferred |
| `ConstraintType` | budget · time · legal · political · scope · explicit_no · **other** |
| `StakeholderRelationship` | client · affected · decision_maker · blocker · **other** |
| `GapCriticality` | load_bearing · useful · minor |
| `GapStatus` | open · asked · answered · assumed |
| `PlanStepStatus` | pending · in_progress · blocked · done |
| `IssueNodeStatus` | open · in_progress · answered · blocked |
| `KnowledgeRefKind` | framework · playbook · company_profile · prior_case · benchmark · **other** |
| `AnalysisStatus` | pending · in_progress · complete · reworking |
| `ReviewCheckName` | mece · evidence_traceable · consistency · calibration · gap_closure |
| `CheckResult` | pass · fail |
| `ReviewVerdict` | approved · needs_rework |
| `ChallengeVerdict` | stands · stands_with_caveats · needs_rework |
| `RecommendationStatus` | draft · gated · accepted · rejected |
| `DeliverableKind` | report · deck · model · **other** |
| `DeliverableStatus` | pending · generated · delivered |
| `GateResult` | pass · fail · loop |
| `PendingKind` | human_input · information · blocker · other |

## Facade (entry point — M1.3)
`Engagement` is the sole public entry point for Engagement State operations, and it
implements `EngagementProtocol` so alternative implementations (file-backed,
AgentDB-backed, testing) can be substituted without changing consumers. The public
API is **frozen** to exactly six operations:

| Operation | Kind | Signature | Purpose |
|---|---|---|---|
| `create` | classmethod | `(engagement_id, tenant_id, slug, created_by="human") -> Engagement` | New engagement as a valid bare state |
| `from_state` | classmethod | `(state: EngagementState) -> Engagement` | Adopt an existing state (**deep-copied on ingest** — the caller's instance is never aliased) |
| `from_json` | classmethod | `(data: str) -> Engagement` | Deserialize from JSON |
| `get_state` | method | `() -> EngagementState` | Read the current state as a **detached deep snapshot**: mutating it (models, lists, dicts — anywhere in the object graph) never affects the engagement; successive calls return equal but distinct objects |
| `validate` | method | `() -> None` | Re-validate; raises on violation |
| `to_json` | method | `() -> str` | Serialize to JSON |

Mutation is performed **only** through the event API (a later sub-milestone), never
by editing state directly; the facade exposes no mutation methods.

> get_state() returns a detached deep snapshot. The operation prioritizes
> correctness and isolation over raw performance. Performance characteristics
> are benchmarked in M1.7.7.

## Stability guarantees
**Lifecycle: Stable** — the Engagement State public API entered the **Stable**
lifecycle on 2026-06-30 (following M1.3 approval). The public surface documented
above is committed; changes follow the rules below.

- **Pre-1.0.** The machine contract is the generated `schema/engagement-state.schema.json`,
  guarded by a drift test. Breaking changes are tracked in `CHANGELOG.md` and require
  an ADR-002 amendment.
- **Stable:** public model names; `EngagementState` field names; existing enum
  values; value-object semantics (`ConfidenceScore` range, `Identifier`/`Reference`
  meaning); the **immutable `id`** contract; "references are by id, never list order."
- **Additive & non-breaking:** new optional fields, new sections, and new enum
  values. `OTHER`/`UNKNOWN` members absorb unrecognized inputs so producers rarely
  need a breaking change.
- **Provisional (may change before 1.0):**
  - `Evidence.source` — under review for a rename to `reference`/`origin` (backlog
    **TD-001**) before external APIs stabilize.
  - `Assumption.owner` — typed `str` now; narrows to an agent enum in M3.
- **Not part of this API:** validators, private modules, and the forthcoming
  event / projection / invariant / persistence machinery. These may change freely;
  interact with the state only through the public models and the `Engagement` facade.
