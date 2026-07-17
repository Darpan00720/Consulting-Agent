---
adr: 010
title: StratAgent as a Consulting Operating System — unify, don't rebuild
status: Proposed
date: 2026-07-17
deciders: [Principal Architect]
relates: [ADR-008 Repository Topology, ADR-009 Deterministic Quant Gate, v2.0 Spec]
tags: [architecture, determinism, evidence, governance, roadmap]
---

# ADR-010 — StratAgent as a Consulting Operating System

> **Status:** Proposed. This is a design + phased roadmap in response to the
> "StratAgent v2.0" specification. It deliberately does **not** change code:
> the change it proposes is large, touches a working revenue-facing pipeline,
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
| **P2** | **Structured analyst output (G2).** Analysts emit `AnalysisBlock` JSON; markdown is rendered from it. | Traceability, provenance | Medium |
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
