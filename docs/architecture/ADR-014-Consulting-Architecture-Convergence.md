---
adr: 014
title: Consulting Architecture Convergence — governing the relationship between app.pipeline and W7–W12
status: Accepted (governance decision; no implementation authorized by this ADR)
date: 2026-07-19
deciders: [Chief Software Architect / Architecture Review Board]
relates: [ADR-009 Deterministic Quant Gate, ADR-010 Consulting Operating System, ADR-011 Consulting Quality Roadmap, ADR-012 Task Routing Layer, ADR-013 Workflow Router]
supersedes: []
tags: [architecture, governance, consulting-methodology, convergence, integration]
---

# ADR-014 — Consulting Architecture Convergence

> **Status:** This is a governance decision record, not an implementation
> record. Per this repo's design-first rule (consistent with ADR-010/011/012/013),
> **no code, no stubs, and no configuration are created or modified by this
> ADR.** It formally closes an architecture-review finding: two independent
> consulting-reasoning systems (`app.pipeline` and `app.consulting`/
> `app.knowledge`/`app.organization`/`app.synthesis`/`app.deliverables`/
> `app.evaluation`, informally "W7–W12") had come to coexist in this backend
> without any document governing their relationship. This ADR is that
> document. It authorizes a governance posture and a phase sequence; each
> phase still requires its own implementation go-ahead before code is
> written, exactly as ADR-011 already requires for its own workstreams.

---

## 1. Title

Consulting Architecture Convergence

## 2. Status

**Accepted** — as a governance decision. Phases 1–2 (§8) are *approved to be
planned*; neither is approved to be implemented by this ADR alone. **Phase 3
is formally closed** (2026-07-19 architecture clarification, §7.3/§8/§11) —
no production adapter for W12 is required or authorized. Phase 4 is
explicitly **not approved** and requires a separate future ADR.

## 3. Context

### 3.1 Current production architecture

`app.pipeline` is the live, deployed consulting engine behind the StratAgent
dashboard (Railway-hosted; real engagement history). It is governed by
ADR-009 (Deterministic Quant Gate), ADR-010 (Consulting Operating System,
phases P1–P3.6), ADR-012 (Task Routing Layer), and ADR-013 (Workflow
Router). Its orchestrator (`app/pipeline/engine.py`, 1,608 lines) runs a
fixed LLM-driven phase sequence — classify → gap_analysis → planning →
framing → issue_tree → analysis → review → challenge → reporting — mirroring
the Claude Code plugin's orchestrator skill, backed by `app.db` (SQLite,
event-sourced), an in-memory SSE bus, and `app.pipeline.providers`'s
failover chain. It owns a deterministic ledger builder, a quant
verification gate, a recommendation ranker, sensitivity/scenario analysis,
and grading. It has 650 passing tests and is under active maintenance
(most recent commits are fixes from a live Codex review). It has no typed
framework catalog and no typed organization/RACI model — framework and
role knowledge exist only as unstructured prompt text in the Claude Code
plugin's agent markdown files.

### 3.2 W7–W12 architecture

A second, independently built consulting-reasoning system exists in the
same backend under `app.consulting` (W7, Workflow Engine), `app.knowledge`
(W8, Knowledge Library — 87 typed frameworks), `app.organization` (W9,
Organization Layer — 25 typed roles, RACI, allocation, governance),
`app.synthesis` (W10, Synthesis & Recommendation Engine), `app.deliverables`
(W11, Deliverables & Presentation Engine), and `app.evaluation` (W12,
Evaluation, Benchmarking & Continuous Improvement Platform). ~27,000 lines,
500 tests, strict one-directional dependency layering (verified
programmatically — zero backward-layer imports). It was, prior to this
ADR, referenced by no ADR, uncommitted to version control in its entirety,
and imported nowhere outside its own package and its own tests.

### 3.3 Findings from the architecture review

An independent architecture review (2026-07-19) found W7–W12 internally
sound after remediating three defects (a registry API naming drift, a
`QualityDimension`/`QualityCheckResult`/`QualityReport` naming collision
between `app.synthesis.models` and `app.deliverables.models`, and
checkpoint/resume boilerplate duplicated four times across layers — all
three fixed, full suite green at 1,154/1,154 both before and after). The
review's central finding was strategic, not technical: **W7–W12 is not
reachable from any live entrypoint, is not part of ADR-011's own roadmap
for closing the audited consulting-quality gap, and its relationship to
`app.pipeline` was undecided.** A follow-up architecture-strategy review
evaluated full replacement, incremental integration, and permanent
reference-architecture status, and selected incremental integration
(Option B): `app.pipeline` remains authoritative; W8 and W9 are additive
and approved for production integration; W12 is additive and approved as
an **offline benchmark/regression-testing subsystem** (its production-
integration scope was subsequently closed — see §3.5); W7 and W10
duplicate live responsibility and are deferred.

### 3.4 Why a decision is required now

Two consulting architectures evolving in the same repository with no
governing document is itself an architectural risk — it produces exactly
the kind of ambiguity ("what is this code *for*?") the review flagged as
the actual release-readiness blocker, independent of either system's
internal quality. This ADR removes that ambiguity permanently by defining
ownership, integration contracts, and a phase sequence, so that no future
contributor has to re-derive the relationship between these two systems
from first principles.

### 3.5 Phase 3 architecture clarification (2026-07-19)

A dedicated architecture-clarification review re-examined §7.3's original
claim that W12 could be adapted to "score a *live* engagement." It found
this claim incorrect, on evidence from W12's own original design
documentation (predating this ADR):

- `app.evaluation.models.BenchmarkCase` requires `engagement_type:
  EngagementCategory` (W7, deferred) and `expected_deliverables:
  DeliverableType` (W11, out of scope) as non-default fields — its own
  module docstring documents this coupling as a **deliberate** design
  choice ("do not duplicate" applied to W7/W11's existing taxonomies), not
  an oversight fixable by a small adapter.
- `app.evaluation.evaluation`'s own docstring defines evaluation as
  "[scoring] a `CaseReplayResult` against the `BenchmarkCase` it
  replayed" — comparison against pre-authored ground truth is not one
  mode among several, it is the *only* mode this module implements.
- `app.evaluation.replay`'s own docstring, describing a possible future
  non-deterministic replay mode, still says evaluating it would be
  "scored against **a case**" — even the module that anticipated future
  extension never described a groundless-scoring mode.
- `app.pipeline.grading` (golden-case grading: user-supplied `{case,
  official answer}` → engagement runs → grader scores the report against
  the gold answer → lessons distilled) performs the same conceptual job
  §7.3 assigned to W12, and was not accounted for when §7.3 was written.
  **Correction (2026-07-19 RC1 adversarial review):** an earlier draft of
  this section overstated `grading.py`'s live status. `app/routers/cases.py`
  (which exposes it via `POST /api/cases/{id}/run`) is **not** mounted in
  `app/main.py` — only `engagements` and `admin` are. `app/main.py`'s own
  comment confirms this was deliberate: *"The public Benchmark and Lessons
  surfaces were removed: every engagement now feeds the learning loop
  automatically... The `cases`/`evals` tables remain for the golden-case
  harness; they are simply not exposed to end users any more."*
  `run_case_eval` is real and tested (`tests/test_api.py`), but only at
  the function level — no test or live route exercises it via HTTP.
  **Corrected position:** the live product's current, actually-reachable
  quality mechanism is the automatic post-engagement reflection/learning
  loop in `engine.py` (fires after every engagement; see §6), not golden-
  case grading specifically. `grading.py` is a real, tested, DB-backed
  internal harness that is currently dormant from an end-user's
  perspective. This correction does not change §3.5's overall conclusion
  — the primary blocker (`BenchmarkCase`'s structural coupling to W7/W11
  and its dependence on pre-authored ground truth) is independent of
  `grading.py`'s mount status and remains fully sufficient on its own to
  keep Phase 3 closed.

**Conclusion:** W12 was correctly built for what its own design intended
(benchmark/regression evaluation of W7–W12's replay engine against its
own curated case library); §7.3, as originally written, asserted a
capability for W12 that neither its design nor `app.pipeline`'s actual
needs support or require. This is corrected below (§6, §7.3, §8, §11).

## 4. Decision

1. **`app.pipeline` remains the sole, authoritative orchestration engine**
   for live consulting engagements. No other module may orchestrate an
   engagement end to end.
2. **W8 Knowledge Library is approved for integration.**
3. **W9 Organization Layer is approved for integration.**
4. **W12 Evaluation Platform is approved for integration as an offline
   benchmark/regression-testing and continuous-quality-improvement
   subsystem over W7–W12's own case library — not for live-engagement
   scoring.** This is a structural conclusion independent of any other
   mechanism `app.pipeline` has or lacks (§3.5): `BenchmarkCase` requires
   ground truth and W7/W11 types no live engagement can supply. `app.pipeline`'s
   actual live quality mechanism today is the automatic post-engagement
   reflection/learning loop (§6); `app.pipeline.grading` (golden-case
   grading) is a real, tested, but currently HTTP-unreachable internal
   harness (2026-07-19 RC1 correction — see §3.5). W12 does not replace,
   duplicate, or require integration with either. No production adapter
   for W12 is required or authorized by this ADR.
5. **W7 Workflow Engine is deferred.** It duplicates `app.pipeline.engine`'s
   lifecycle responsibility; no integration work against it is authorized
   by this ADR.
6. **W10 Synthesis Engine is deferred.** It duplicates
   `app.pipeline.ledger_builder`/`evidence_*`'s reasoning-chain
   responsibility; no integration work against it is authorized by this
   ADR.
7. **No replacement of `app.pipeline` is approved**, in whole or in part,
   by this ADR. Any future proposal to replace or substantially rework
   `app.pipeline`'s orchestration or evidence model requires its own ADR
   and is explicitly out of scope here.

## 5. Architecture Principles

These principles bind every future integration PR under this ADR:

- **Single production orchestrator.** `app.pipeline.engine` is the only
  module permitted to run an engagement lifecycle end to end. Integrated
  W7–W12 modules are called *by* it; they never call it, wrap it, or run
  a competing lifecycle alongside it.
- **Clear ownership.** Every responsibility has exactly one owner (§6).
  A responsibility is never split silently between `app.pipeline` and an
  integrated module without this ADR (or its successor) saying so
  explicitly.
- **Adapter-based integration.** `app.pipeline` never imports W8/W9/W12
  internals directly into its orchestration logic. Each integration point
  is a thin adapter module that translates between `app.pipeline`'s data
  shapes and the target module's public API.
- **No duplicated orchestration.** No integrated module may introduce its
  own engagement-lifecycle state machine, stage sequence, or checkpoint
  loop. That remains `app.pipeline`'s alone.
- **No direct cross-layer coupling.** Integrated modules do not import
  `app.pipeline` internals, and `app.pipeline` does not import W7 or W10
  at all under this ADR.
- **Stable public APIs only.** Integration consumes only each module's
  already-tested public surface (`app.knowledge.registry`,
  `app.organization.registry`/`allocation`) — never a private
  (`_`-prefixed) symbol, never an internal data structure reached by
  reflection. (W12 has no production integration surface — §7.3.)
- **Incremental migration.** Each phase in §8 ships independently and is
  individually reversible; no phase is contingent on a later phase's
  success.
- **Feature-flagged rollout.** Every integration point ships behind a
  flag defaulting to off in production until explicitly enabled.
- **Backward compatibility.** No integration phase changes `app.pipeline`'s
  existing SSE event contract, DB schema, or public HTTP API surface.

## 6. Ownership Matrix

| Responsibility | Owner | Notes |
|---|---|---|
| `app.pipeline` (orchestration engine itself) | `app.pipeline` | Unchanged by this ADR |
| Consulting lifecycle (phase sequencing, stage progression) | `app.pipeline` | W7 remains deferred; does not own this in production |
| LLM orchestration (provider selection, failover, prompts) | `app.pipeline` | Unaffected |
| State management (engagement persistence, SSE, DB) | `app.pipeline` | Unaffected |
| Framework catalog | `app.knowledge` (W8) | Approved; `app.pipeline` consumes via adapter, does not reimplement |
| Organization / role / RACI model | `app.organization` (W9) | Approved; consumed via adapter |
| **Live post-engagement quality signal (automatic, every engagement)** | **`app.pipeline` (`engine.py` reflection/learning loop)** | **Pre-existing, live, fires after every completed engagement. This is the product's actual current live quality mechanism (2026-07-19 RC1 correction).** |
| Golden-case grading (ground-truth comparison harness) | `app.pipeline` (`grading.py`) | Real, tested at the function level, DB-backed — but `app/routers/cases.py` is not mounted in `app/main.py`, so it is not currently reachable via any live HTTP endpoint (deliberate removal, per `main.py`'s own comment). W12 does not replace or duplicate it either way (§3.5). |
| Offline benchmark / regression / hallucination-detection evaluation of W7–W12's own replay engine | `app.evaluation` (W12) | Approved as an internal-only subsystem scoring `CaseReplayResult` against `app.evaluation.case_library`'s own curated cases; no `app.pipeline` integration point exists or is required (§7.3) |
| Deliverables / presentation | `app.pipeline` (reporting/grading) | W11 remains out of scope for this ADR; not approved, not deferred-with-intent — simply not addressed, revisit separately if desired |
| Evidence | `app.pipeline` (`evidence_schema`/`evidence_normalizer`/`evidence_store`) | W10's evidence chain is deferred; no change of ownership |
| Recommendations | `app.pipeline` (`recommendation_ranker`, ledger) | W10's recommendation chain is deferred; no change of ownership |
| Reporting | `app.pipeline` (`grading`, report generation) | Unaffected |

## 7. Integration Contracts

### 7.1 `app.pipeline` → W8 (Knowledge Library)

- **Permitted:** `app.pipeline` may call `app.knowledge.registry.FrameworkRegistry`'s
  public lookup methods (`get`, `list`, `find_by_*`) and
  `app.knowledge.selection.select_frameworks` through a dedicated adapter
  module, to supply structured framework metadata into its existing
  prompt-construction step.
- **Prohibited:** importing `app.knowledge.catalog`'s private `_Spec`/
  `_SPECS` symbols directly; mutating a `FrameworkDefinition` in place;
  bypassing `FrameworkRegistry` to hand-parse the catalog module.

### 7.2 `app.pipeline` → W9 (Organization Layer)

- **Permitted:** `app.pipeline` may call
  `app.organization.registry.OrganizationRegistry`'s public lookup methods
  and `app.organization.allocation.allocate_team` through an adapter, to
  turn its existing free-text staffing suggestions into typed role
  assignments.
- **Prohibited:** calling `app.organization.governance`/`review` (these
  belong to W9's own approval workflow, which is not part of this
  integration); importing `RoleDefinition` internals to hand-construct a
  role.

### 7.3 `app.pipeline` → W12 (Evaluation Platform) — CLOSED, no production integration

**2026-07-19 correction.** This section originally authorized a live-
engagement adapter. That authorization is withdrawn — see §3.5 for the
evidence. Summary: `app.evaluation.evaluate_replay`/`detect_hallucinations`
require a full `BenchmarkCase`, which (a) requires `EngagementCategory`
(W7, deferred) and `DeliverableType` (W11, out of scope) as non-default
fields, and (b) requires pre-authored ground truth (`expected_findings`/
`expected_recommendations`) that does not exist for a novel client
engagement. Both are structural properties of W12's design, not
implementation gaps — sufficient on their own, independent of any other
mechanism `app.pipeline` has (§3.5, corrected 2026-07-19).

- **Permitted:** nothing — there is no `app.pipeline` → W12 production
  integration point. `app.evaluation` remains usable standalone, by
  W7–W12 contributors, to benchmark/regression-test W7–W12's own replay
  engine against `app.evaluation.case_library`'s curated cases. This
  requires no `app.pipeline` involvement and is unaffected by this
  closure.
- **Prohibited:** building any adapter that fabricates `BenchmarkCase`
  ground-truth fields from live engagement data (this would violate the
  "no new reasoning" principle applied in Phases 1–2); importing
  `app.consulting.models.EngagementCategory` or
  `app.deliverables.models.DeliverableType` into `app.pipeline` for this
  purpose (this would violate §5's "no direct cross-layer coupling" and
  §4's W7/W11 deferral); `app.pipeline` calling
  `app.evaluation.replay.replay_case` (unchanged from the original
  prohibition — still applies for the same reason).

### 7.4 Universally prohibited, across all three integrations

- No imports of private (`_`-prefixed) modules or symbols in either
  direction.
- No direct access to another package's internal registry/dict state —
  only through the registry's own public methods.
- No shared mutable state between `app.pipeline` and any W7–W12 module
  (each side owns its own data; an adapter copies/translates, it does not
  alias).
- All communication through public, already-tested interfaces only — if
  the interface needed doesn't exist yet, it is added to the target
  module's own public API (with its own tests) before the adapter is
  built, never reached around.
- `app.pipeline` does not import `app.consulting` (W7) or `app.synthesis`
  (W10) under this ADR, in any form, for any reason.

## 8. Migration Strategy

Architecture only — no implementation detail, no code, no file changes
authorized by this section.

- **Phase 0 — Governance.** Commit W7–W12 to version control in its
  entirety (it is currently untracked). This ADR is the record of that
  decision; the commit itself is a separate, explicit action requested by
  the repository owner, not authorized automatically by this document.
  No integration code is written in Phase 0.
- **Phase 1 — Knowledge.** Design and approve the `app.pipeline` ↔
  `app.knowledge` adapter contract (§7.1). Gated on its own
  implementation go-ahead before any code is written.
- **Phase 2 — Organization.** Design and approve the `app.pipeline` ↔
  `app.organization` adapter contract (§7.2). Independently gated;
  does not depend on Phase 1's completion.
- **Phase 3 — Evaluation. CLOSED (2026-07-19), no production adapter.**
  The architecture-clarification review (§3.5) found no valid production
  integration point exists — see §7.3. W12 remains an offline
  benchmark/regression-testing subsystem for W7–W12's own use; no further
  Phase 3 work is scheduled.
- **Phase 4 — Future reassessment of Workflow/Synthesis.** Not scheduled,
  not approved, not authorized by this ADR. If `app.pipeline`'s lifecycle
  or evidence/reasoning model is ever reassessed, that reassessment
  produces its own ADR, informed by whatever W7 and W10 have become by
  then — this ADR neither commits to nor rules out that future decision.

## 9. Risk Management

*(Applies to Phases 1–2. Phase 3 is closed — §3.5/§7.3/§8/§11 — and ships
no adapter, so none of the below applies to it.)*

- **Rollback philosophy.** Every phase (1–2) is purely additive to
  `app.pipeline` — disabling the phase's feature flag fully reverts
  observable behavior to pre-integration state. No phase modifies
  `app.pipeline`'s existing state model, so rollback is never a data
  migration.
- **Feature flags.** Each integration point ships disabled by default;
  enabling one phase's flag has no dependency on another phase's flag.
- **Database isolation.** Before any phase ships, the shared
  `MemoryType.CONSULTING` / `app.db` keyspace risk identified by the
  architecture review must be closed — W7–W12's checkpoint helpers
  (`app.memory.checkpoint`) must not write into the same key space
  `app.pipeline`'s live event log uses without an explicit, reviewed
  namespace separation. This is a precondition for Phase 1, not a
  follow-up.
- **API compatibility.** No phase changes `app.pipeline`'s SSE contract,
  DB schema, or HTTP API surface (per §5). Any adapter-side API needed on
  the W8/W9/W12 side is added as new, additive surface with its own
  tests — never a breaking change to an existing public method.
- **Versioning.** W8's framework catalog and W9's role catalog are
  already version-aware (`FrameworkRegistry`/`OrganizationRegistry`
  support multiple versions per id); adapters must pin the version they
  integrate against explicitly, not float to "latest" implicitly.
- **Testing expectations.** Each phase ships with: (a) tests for the new
  adapter itself, (b) a regression run of `app.pipeline`'s full existing
  suite with the feature flag off (must be unchanged), and (c) a
  regression run with the flag on (must not break any existing
  `app.pipeline` test). No phase is considered complete without all
  three.

## 10. Consequences

**Positive:** ends the ambiguity the architecture review flagged as its
central finding; gives `app.pipeline` a typed framework catalog and
org/RACI model it currently lacks entirely (a capability gap distinct
from, and not previously identified by, ADR-011's own roadmap — see §12);
preserves a working, live product without introducing the risk of a
big-bang rewrite; keeps W7 and W10's substantial engineering investment
available for a future, deliberate decision rather than discarding it.
The Phase 3 closure (§3.5) is also a positive outcome, not a shortfall: it
prevented building a redundant second evaluation mechanism alongside the
product's actual live quality signal (the automatic reflection/learning
loop), and it surfaced that neither that loop nor `app.pipeline.grading`
has a governing ADR of its own (a pre-existing documentation gap, noted
under Known limitations below, not created by this ADR).

**Trade-offs:** `app.pipeline` and W7/W10 continue to duplicate lifecycle
and evidence-reasoning responsibility indefinitely, until Phase 4 (if it
ever happens) — this is an accepted, explicit trade-off, not an oversight.
Two consulting-quality philosophies (LLM-judgment-driven vs.
deterministic/typed) now coexist in the same product by design. W12
remains fully built but permanently disconnected from live production
value, usable only for W7–W12's own internal benchmarking — a smaller
return on its ~engineering investment than originally intended, accepted
here as the honest, evidence-based outcome rather than forced further.

**Known limitations:** this ADR does not address W11 (Deliverables)
ownership — it is neither approved for integration nor formally deferred;
a future ADR amendment should resolve this gap explicitly. This ADR also
does not resolve the pre-existing naming collision between
`app.workflow.router` and `app.pipeline.router` (flagged by the
architecture review as out of scope for that review); it remains out of
scope here too. Neither `engine.py`'s reflection/learning loop (§6's actual
live quality mechanism) nor `app.pipeline.grading` (the dormant golden-case
harness — see §3.5's 2026-07-19 correction) has a governing ADR of its own
anywhere in this repository; this ADR does not create one (out of scope),
but future documentation work should.

**Future review points:** revisit this ADR if `app.pipeline`'s evidence
model or lifecycle needs a structural change for reasons independent of
W7/W10 (that would be the natural trigger for a Phase 4 proposal); revisit
if Phase 1–3 integration reveals the adapter boundary is more porous than
assumed.

## 11. Acceptance Criteria

Before **Phase 1** may begin: W7–W12 committed to version control (Phase
0 complete); the `MemoryType.CONSULTING`/`app.db` namespace-isolation risk
closed; a named adapter-contract design for §7.1 reviewed and approved.

Before **Phase 2** may begin: same namespace-isolation precondition
(shared with Phase 1, not re-verified per phase); a named adapter-contract
design for §7.2 reviewed and approved. Does not require Phase 1 to have
shipped.

**Phase 3 is closed; no acceptance criteria apply.** No production adapter
is required or authorized (§3.5, §7.3). This is recorded as an
architectural clarification, not a cancelled feature: the investigation
determined production integration would require either fabricated ground
truth or coupling to deferred/out-of-scope layers to even attempt —
sufficient reason on its own — and would additionally duplicate the
product's real live quality mechanism (the automatic reflection/learning
loop; `app.pipeline.grading` itself is a real but currently HTTP-unreachable
harness, corrected 2026-07-19 — see §3.5).

Before **Phase 4** may even be proposed: a separate ADR, independently
justified, is drafted and goes through this project's normal design-first
review — this ADR grants no standing authorization for it.

## 12. Related ADRs

- **ADR-009 (Deterministic Quant Gate):** unaffected. `app.pipeline`'s
  quant verification remains untouched by any phase in this ADR.
- **ADR-010 (Consulting Operating System):** this ADR is a direct
  successor in spirit. ADR-010 §4's "target architecture" diagram predates
  both `app.pipeline`'s actual implemented shape (§6a–6d of that ADR) and
  W7–W12; it should carry a pointer to this ADR for the current governance
  answer, rather than being redrawn to match either system after the fact.
- **ADR-011 (Consulting Quality Roadmap):** **correction, made during the
  2026-07-19 documentation consistency audit** — an earlier draft of this
  section overstated the relationship, claiming Phase 1/2 integration
  would satisfy several of ADR-011's 48 workstream items. On inspection,
  ADR-011's Workstream H (Knowledge Management) and K (Framework
  Improvements) govern `knowledge-vault/*.md` and
  `packages/knowledge/retrieval_adapter.py` — the Claude Code plugin's
  prose knowledge base — which is a **different artifact** from W8's
  `app.knowledge` (a typed Python framework catalog for `app.pipeline`'s
  own deterministic selection/execution logic). Likewise, ADR-011 has no
  workstream analogous to W9's organization/RACI model — its "role"
  mentions concern board-simulation personas (G2) and organizational-
  readiness *scoring* (B-series), not team staffing. **Corrected
  position:** this ADR's Phase 1/2 integration does not close any ADR-011
  workstream item; the two roadmaps address genuinely separate knowledge
  systems and should not be conflated. ADR-011 is updated (this audit) to
  note this ADR's existence for readers who might otherwise assume overlap.
- **ADR-012 (Task Routing Layer) / ADR-013 (Workflow Router):**
  unaffected. Neither routing layer changes; W7–W12 integration happens
  entirely within `app.pipeline`'s existing orchestration. (ADR-013's
  Workflow Router is itself still "Proposed / design only" and not
  currently wired into `app.pipeline` either — its status is independent
  of this ADR and not evaluated here.)
