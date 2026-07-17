---
adr: 010
title: StratAgent as a Consulting Operating System — unify, don't rebuild
status: Accepted (P1 + P2 implemented 2026-07-17)
date: 2026-07-17
deciders: [Principal Architect]
relates: [ADR-008 Repository Topology, ADR-009 Deterministic Quant Gate, v2.0 Spec]
tags: [architecture, determinism, evidence, governance, roadmap]
---

# ADR-010 — StratAgent as a Consulting Operating System

> **Status:** Accepted; P1 (Deterministic Ledger Builder) and P2 (Structured
> Evidence Platform) are implemented and merged — see §6/§6a. P3 (full core
> unification), P4 (Business-Plausibility Engine), and P5 (Board Simulation)
> remain future work, each requiring its own go-ahead. This is a design +
> phased roadmap in response to the "StratAgent v2.0" specification. Every
> phase touches a working revenue-facing pipeline,
> and the project's standing rule is design-first with an approval gate. The
> v2.0 spec agrees ("architecture before prompting", "understand architecture
> before changing code", "never rush").

---

## 1. The single most important finding

**StratAgent already contains ~70% of the v2.0 "target architecture" — it just
isn't wired into the live product.** The v2.0 spec reads as a greenfield build
("create deterministic services: Quant Engine, Ledger Builder, Evidence
Registry, Assumption Registry, Consistency Engine…"). But `packages/` already
has, as frozen, strictly-typed, tested code:

| v2.0 asks for | Already exists in `packages/` |
|---|---|
| Evidence Registry, Source/Confidence Registry | `state/ledgers.py` `Evidence`, `EvidenceType`; `evidence/registry.py` `ProviderRegistry`; evidence lifecycle events (`EvidenceAdded/Validated/Rejected/MarkedStale`) |
| Assumption Registry | `state/ledgers.py` `Assumption`, `AssumptionStatus`; `AssumptionAdded/Updated/Invalidated` events |
| Structured analyst evidence (not prose) | `analysis/contracts.py` `AnalysisBlock` + `validate_analysis_block`, `FindingRecorded` |
| Consistency Engine / deterministic validation | `reporting/validation.py` `validate_consistency`, `check_render_ready` |
| Governance-before-recommendation | `governance/gates.py` (reviewer/challenger/reporting gates) |
| Quant Engine / Formula & Unit Validator | `apps/dashboard/.../quantcheck.py` (ADR-009 — the one deterministic service already on the LIVE path) |
| Observability | `telemetry/` (the one core package the live app *does* import) |

**The problem is not missing architecture. It is a fork** (ADR-008): a rich
deterministic core that production doesn't use, and a live dashboard that passes
markdown between LLM calls with exactly one deterministic component (the Quant
Gate). Every failure we have observed this session traces to that fork.

**Therefore v2.0 is a UNIFICATION project, not a rebuild.** Rebuilding from
scratch would throw away 954 tests of working, typed domain logic and re-derive
it worse. The correct move is to make the live path stand on the core.

## 2. Evidence this is the right diagnosis

Seven of seven live engagements this session (EspressoLux, NordWear, Meridian,
MediCore, + 3 grocery retries) failed the Quant Gate for the **same** reason:
**an LLM (the Engagement Manager) is asked to hand-compose a 30–50 row JSON
ledger** — valid JSON, globally unique IDs, correct formula wiring, consistent
units, closed bridges — and free-tier models cannot reliably do it on a dense
case. This is precisely what the v2.0 principle "**LLMs must not invent
calculations / No LLM is allowed to generate ledgers**" forbids, and it is the
current architecture's single biggest defect. The ledger should be **assembled
by code** from structured evidence the LLM emits, not authored by the LLM.

## 3. The four real gaps (what v2.0 adds beyond unification)

Unifying gets us the registries, consistency engine, and governance. Four
genuinely new capabilities remain:

- **G1 — Deterministic Ledger Builder.** Analysts emit typed *evidence atoms*
  (metric, value, unit, source, confidence, assumption-or-fact); code — not the
  EM — assembles the canonical ledger, mints IDs, wires formulas from declared
  dependencies, and reconciles collisions by rule. *This is the fix for the 7/7
  failure and the highest-leverage change in the entire spec.*
- **G2 — Structured-only analyst output.** Analysts today emit prose with inline
  `[ASSUMPTION]` labels. Target: they emit `AnalysisBlock`/evidence JSON
  (schema already exists), and prose is *rendered from* structured data, never
  the source of truth.
- **G3 — Business-Plausibility Engine.** A dedicated check (part deterministic
  bands, part LLM) that every recommendation passes operational / financial /
  organizational / timeline feasibility — independent of the Challenger. Today
  the Challenger (one LLM) carries this implicitly.
- **G4 — Board Simulation.** A persona panel (CEO/CFO/COO/CIO/CHRO/Chair/
  Investor/Audit) that pressure-tests the recommendation for approvability
  before it ships. Net-new.

## 4. Target architecture (unified)

```
LIVE PIPELINE (rebuilt on packages/ core)
  Layer 1  Case Understanding      → StructuredCaseDefinition (typed)
  Layer 2  Problem Structuring     → IssueTree + Hypotheses (typed, MECE-checked)
  Layer 3  Research (analysts)     → EVIDENCE ATOMS ONLY (AnalysisBlock/Evidence)
  Layer 4  Evidence Layer          → EvidenceRegistry + AssumptionRegistry (exists)
  ── deterministic services (code, no LLM) ─────────────────────────────
  Ledger Builder (G1) → Formula Validator → Unit Validator →
  Consistency Engine (exists) → Quant Gate (exists, ADR-009)
  ── strategic reasoning (LLM) ─────────────────────────────────────────
  Options → Trade-offs → Scenarios → Risk → Roadmap
  ── independent validation ────────────────────────────────────────────
  Business-Plausibility Engine (G3) → Reviewer → Challenger → Board Sim (G4)
  ── deliverable ───────────────────────────────────────────────────────
  Report Writer (renders from verified structures; cannot introduce a number)
```

The two things an LLM may never touch — **fact values and calculations** — are
walled off behind the deterministic services. The report writer's tie-out
(ADR-009) already enforces "no number in the report that isn't in the ledger";
G1 closes the loop on the other side (no number in the ledger the LLM authored).

## 5. Phased roadmap (each phase ships independently, gated by tests)

| Phase | Deliverable | Fixes | Risk |
|---|---|---|---|
| **P1** ✅ | **Deterministic Ledger Builder (G1).** DONE (2026-07-17). `ledger_builder.py`: EM emits a ```atoms block; code mints ids, translates key-refs→id-formulas, **computes every derived value** (LLM value ignored), emits the ```quant block the gate verifies. Wired into `quant_verified`; builder errors feed the existing rework loop; backward compatible (no atoms block → pass-through). 16 tests. | The 7/7 failure | Medium — changes EM + analyst contracts |
| **P2** ✅ | **Structured Evidence Platform (G2).** DONE (2026-07-17). Analysts emit `evidence` atoms (own domain, own provenance); a Validator/Normalizer/Store pipeline aggregates them into one canonical, deduplicated, unit-consistent set that seeds the EM's reconciliation. 30 tests. | Traceability, provenance, upstream data quality | Medium |
| **P3** | **Unify onto the core.** Live pipeline builds a real `EngagementState` (state/evidence/governance packages) instead of passing markdown; retires the dashboard's parallel logic. Resolves ADR-008. | Duplication, drift | High — largest migration |
| **P4** | **Business-Plausibility Engine (G3).** | Unrealistic recommendations | Low |
| **P5** | **Board Simulation (G4).** | Approvability | Low |

**Sequencing rationale:** P1 alone plausibly moves the pass rate from 0/7 toward
passing on complex cases — it attacks the observed root cause directly and is
mostly additive (the Quant Gate that verifies its output already exists). P3 is
the big architectural win but also the biggest risk, so it comes after P1/P2
have de-risked the evidence-atom contract that P3 depends on.

## 6. Recommended first slice (P1) — contract

`apps/dashboard/backend/app/pipeline/ledger_builder.py` (stdlib + the existing
`quantcheck` types), plus prompt-contract changes so analysts emit atoms:

```json
// each analyst emits a list of these; the EM emits NONE of the ledger itself
{ "metric": "Delivery commission drain", "value": 9.72, "unit": "EUR_M",
  "basis": {"scope": "annual"}, "kind": "derived",
  "formula": {"op": "mul", "inputs": ["delivery_share","commission_rate","revenue"]},
  "source": "analyst_estimate", "confidence": "medium", "low": 0.15, "high": 0.25 }
```

`build_ledger(atoms) -> QuantLedger`:
- mints canonical IDs (A1, A2, … / D1, D2, …), de-duplicates identical metrics,
- resolves collisions deterministically (conservative value wins; logged),
- compiles `formula` trees into the exact `quantcheck` formula strings,
- emits the `quant` block that the existing verifier (ADR-009) then checks.

The LLM supplies *evidence*; code supplies *structure and arithmetic*. The Quant
Gate remains the proof. This is testable in isolation with golden atom-sets
(including the EspressoLux/MediCore atoms) and does not require the P3 migration.

## 6a. Phase 2 — Structured Evidence Platform (implemented 2026-07-17)

**Goal:** move the *last* place an LLM invents structure — analysts writing
free prose the Engagement Manager has to re-derive atoms from — into typed,
validated, normalized evidence. P1 fixed "the EM authors the ledger"; P2 fixes
"the EM has to reverse-engineer atoms from five paragraphs of prose."

**Target pipeline (spec's Task 6), realized inside the existing asyncio
orchestrator — not a new framework.** The spec's diagram names LangGraph;
this codebase has no LangGraph anywhere (orchestration is `engine.py`'s plain
sequential `phase()`/`run_analyst()` calls). Introducing a new orchestration
framework would itself violate the phase's own "reuse, don't duplicate"
principle, so Task 6's *shape* — Analysts → Evidence Validator → Evidence
Normalizer → Evidence Store → Ledger Builder → Quant Gate → existing review
flow — is implemented as four new steps inside the existing orchestrator:

```
5 analysts (parallel domains, own ```evidence block each)
        │  each analyst's block validated INDEPENDENTLY
        ▼
Evidence Validator   (evidence_schema.py)   — malformed block REJECTED, not passed on
        ▼
Evidence Normalizer  (evidence_normalizer.py) — units/currency/%/confidence/alias/dedup
        ▼
Evidence Store       (evidence_store.py)    — canonical, queryable, one per engagement
        ▼
   .to_atoms_block()  ── bridges into Phase 1, UNCHANGED ──▶  Ledger Builder ──▶ Quant Gate
        ▼ (seeded into, not replacing, the EM's context)
Engagement Manager   — resolves any flagged conflicts, re-emits final ```atoms
        ▼
   reviewer → challenger → report-writer   (ADR-006, untouched)
```

The Engagement Manager is **not removed** (the spec's diagram omits it, but
deleting it would be exactly the kind of "redesign P1" the brief forbade).
Its job shrinks from "invent atoms from prose" to "resolve the handful of
conflicts the Normalizer could not adjudicate" — judgment stays a judgment
call, structure stops being one.

### Canonical evidence schema (v1)

`app/pipeline/evidence_schema.py`, `EvidenceAtom` (frozen dataclass),
`SCHEMA_VERSION = 1`:

| Field | Notes |
|---|---|
| `schema_version`, `atom_id`, `category`, `type`, `title`, `unit` | always required |
| `scope` | **added beyond the spec's example list** — P1's Quant Gate uses a time-basis scope (`"annual"` vs `"cumulative_3yr"`) to catch basis-mixing; omitting it would make the Store→Ledger-Builder bridge lossy relative to what P1 already verifies. Justified by the phase's own "reuse ADR-009" principle. |
| `description`, `confidence`, `confidence_reason` | advisory |
| `value` | facts/assumptions only; a `derived` atom's stray value is *ignored*, never trusted (same P1 discipline) |
| `source_type`, `source_reference` | required for facts/assumptions ("missing provenance" is a hard reject) |
| `assumptions`, `dependencies` | lists of other atoms' `atom_id` |
| `formula` | derived atoms only, over other atoms' `atom_id` — never over ids, since ids don't exist until the Store bridges to Phase 1 |
| `low`, `high`, `anchor`, `bridge` | same semantics as P1's ledger entries |
| `created_by`, `created_at` | provenance — which analyst, when |
| `validation_state`, `status` | lifecycle (below) |

**Versioning:** `_ALLOWED_FIELDS` is an explicit allow-list; a v2 schema adds
fields to it but must not repurpose or remove a v1 field, so a v1 atom is
always readable by v2+ code without a migration pass.

### Evidence lifecycle

```
unvalidated  →  (Schema)     rejected  (malformed — dropped, analyst's prose still used)
             │
             ▼  valid
   open      →  (Normalizer) normalized  (units/currency/%/confidence canonicalized,
             │                            aliases merged, exact duplicates collapsed)
             ▼
   conflict  ←  two analysts defined the same (post-alias) atom_id differently —
                BOTH kept, tagged, surfaced to the EM as a `key__creator` dangling
                reference at ledger-build time (never silently adjudicated)
             │
             ▼  EM resolves
   resolved  →  folds into the canonical ```atoms block Phase 1 verifies
```

### Validation rules enforced (Task 5)

Schema-layer (hard reject, whole block thrown out — an analyst's evidence is
all-or-nothing): unknown fields, wrong types, invalid category/type/confidence
shape, missing required fields, missing provenance, duplicate `atom_id` within
one block, malformed formula (reusing P1's AST parser — same sandboxed
`+ - * / **` grammar, no calls/attributes/imports reachable), a formula
referencing no other atom, a dependency that isn't a slug, an assumption whose
value sits outside its own low/high band.

Normalizer-layer (soft, corrects representation, never invents a value):
currency/unit spelling (`"$M"` → `USD_M`), percentage→ratio (converting the
*band* together with the value — a real bug caught and fixed during this
implementation: converting only the value while leaving a percentage-scaled
band produces an atom that fails its own bounds check), confidence synonyms
and numeric confidences → the 3-level scale, alias resolution (explicit map +
normalized-title matching), duplicate collapse.

### Migration strategy / backward compatibility (Task 7)

No forced cutover. Three fallback layers, each independently tested:

1. One analyst's evidence block is malformed → **that analyst's atoms are
   dropped**, its prose still reaches the EM exactly as before Phase 2. The
   engagement does not fail.
2. **Every** analyst produces no evidence block at all (the entire pre-Phase-2
   world, including today's mock mode) → the Evidence Store is empty, the EM
   receives no pre-validated seed section, and falls back to **exactly**
   Phase 1's tested from-prose atom authoring. Verified: all 139 pre-Phase-2
   tests pass unmodified after this phase's changes.
3. A genuine cross-analyst conflict is never silently resolved by the
   Normalizer — it is surfaced as a dangling `key__creator` reference at
   ledger-build time, which routes back to the EM's existing rework loop
   (unchanged from Phase 1).

### Known limitations

- **The Store is in-process and per-engagement, not persisted.** It is built
  fresh from that run's analyst atoms and discarded after reconciliation.
  Persisting the evidence lifecycle durably (a DB migration, retention policy,
  query surface across engagements) is a separate, larger decision the phase's
  own scope ("focus exclusively on the evidence platform") does not take on.
- **Token budget trade-off.** Analysts run on a free-tier chain with a hard
  ~2000-token output cap. The prose lead was cut from "under 500 words" to
  "under 120 words" to make room for the evidence block — a real, deliberate
  trade rather than an oversight; structured atoms are more information-dense
  per token than prose, which is the actual point of the phase, but it means
  less narrative color reaches the reviewer/report-writer than before.
- **Alias resolution is a small explicit map + literal title-normalization,
  not semantic matching.** Two analysts naming the same concept in genuinely
  different words (not synonyms in `ALIAS_MAP`, not near-identical titles)
  will not be merged and may surface as a false "conflict" for the EM to
  resolve — a false positive is safe (it costs one EM judgment call), a false
  merge would not be, so the asymmetry is intentional.
- **Not yet proven on a live, complex, real engagement.** P1's mechanism was
  validated the same way (unit tests + mock e2e) before a live MediCore-class
  run was the actual proof; the same live validation step is the natural next
  action for P2, not yet performed.

### Future extensibility

- A v2 schema can add fields (e.g. a numeric confidence interval alongside the
  3-level label) without breaking v1 atoms already in flight.
- `evidence_store.py`'s lookup surface (`by_category`, `by_source`,
  `dependents_of`, `provenance`) is designed to be exactly what a future
  Business-Plausibility Engine (P4) or Board Simulation (P5) would query
  against — those phases can read the Store directly rather than re-deriving
  structure from a report, without any change to this phase's code.
- If evidence *does* eventually need to persist across engagements (e.g. to
  detect "this assumption has been wrong three engagements running"), the
  Store's atoms are already the right shape to write to a table — that would
  be an additive persistence layer behind the same `EvidenceStore` interface,
  not a redesign.

## 7. What I am asking to decide

1. **Adopt the "unify, don't rebuild" thesis** (§1) — i.e. v2.0 is delivered by
   phasing onto `packages/`, not a greenfield rewrite.
2. **Approve P1 as the first build** (deterministic Ledger Builder) — the
   highest-leverage, most self-contained slice, directly targeting the 0/7
   ledger-generation failure.
3. **Confirm the phase order** (P1 → P2 → P3 → P4 → P5), accepting that P3 (full
   core unification) is a larger, separately-approved migration.

## 8. Consequences

- **+** Delivers the spec's determinism guarantees by *reusing* proven code, not
  re-deriving it; the biggest current defect (LLM-authored ledgers) is fixed
  first.
- **+** Each phase ships behind the existing test gate; the working product is
  never left broken between phases.
- **−** This is weeks of work, not one session. Anyone expecting the entire OS
  in a single pass will be disappointed — deliberately, per the spec's own
  "prefer correctness over speed."
- **−** P3 carries real migration risk to a live pipeline; it must not be
  rushed, and is gated on P1/P2 proving the evidence-atom contract.
