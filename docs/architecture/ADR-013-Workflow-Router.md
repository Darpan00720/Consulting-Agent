---
adr: 013
title: Workflow Router — classify task-type and select the agent, above the Provider Router
status: Proposed (design only; revised 2026-07-18 to resolve review findings F1–F4 — classifier-only, Target interface, unit-of-work model, Graphify-as-tool)
date: 2026-07-18
deciders: [Principal Architect]
relates: [ADR-010 Consulting Operating System, ADR-012 Task-Routing Layers, ADR-014 Consulting Architecture Convergence, Engineering-Workflow.md]
supersedes: []
tags: [architecture, routing, orchestration, workflow, agents]
---

# ADR-013 — Workflow Router

> **Status:** Design document, not an implementation record. Per this repo's
> design-first rule (and consistent with ADR-010/011/012), **no code, no stubs,
> and no configuration are created by this ADR.** It is the design for the
> upper of the two routing layers ADR-012 §6.1 named; ADR-012 is unchanged.

> **Scope boundary up front.** The Workflow Router is a **classifier + selector**
> that sits above the dispatcher — it decides *which agent/toolchain should own a
> unit of work*; the host (Claude Flow) performs the actual dispatch (§2a).
> Most targets (Codex, Claude Code, Graphify) are engineering/dev-stack tools,
> not the dashboard product's runtime. The one category that reaches the product
> runtime is **business consulting**, which selects StratAgent's governed agents
> (the `solve-case` pipeline). This ADR is explicit about which context each
> category lives in, the same honesty ADR-012 applied when it refused to route
> task-types at the provider seam.

> **Revision (2026-07-18) — review findings F1–F4 resolved.** Independent review
> flagged three blocking under-specifications and one taxonomy error. This
> revision resolves them: **F2** — the router is a **classifier + selector only;
> Claude Flow remains the dispatcher** (§2a, Option A). **F1** — a formal
> `Target` interface is now defined (§4a). **F3** — "unit of work," the routing
> trigger, lifetime, `RoutingContext` marker propagation, and recursion
> prevention are specified (§6a). **F4** — Graphify is a **tool a target uses**,
> not a dispatch target (§3/§4/§5 corrected). All affected diagrams, tables,
> responsibilities, and phases are updated for consistency.

---

## 1. Motivation — why task routing and provider routing are separate concerns

**Two different questions, at two different altitudes:**

- **Workflow routing** (this ADR): *what kind of work is this, and which
  agent/toolchain should do it?* — "this is a refactor → Codex"; "this is a
  consulting case → the solve-case pipeline." Decided **once per unit of work**,
  from the work's *type*.
- **Provider routing** (ADR-012): *for this one LLM call, which provider/model
  serves it?* — "this call carries an image → a vision-capable provider."
  Decided **per LLM call**, from the call's *intrinsic capability needs*.

The dividing line (ADR-012 §3): a decision is **provider-level** iff it can be
made from the intrinsic properties of a single prompt matched to a model
capability; a decision that requires knowing *what kind of work this is* is
**workflow-level**.

### The concrete harm of conflating them (observed, not hypothetical)

ADR-012's own history is the evidence. A "documentation" routing rule was first
implemented **at the provider seam** — a task-type masquerading as a provider
capability. It could only survive there as a proxy ("prefer Gemini because prose
is fluent"), its real targets (Claude Code, Codex) weren't provider-chain
families at all, and it had to be **reverted** (ADR-012 §13.1 correction). The
lesson, paid for once: task-type belongs to a layer whose targets are agents,
not providers. Conflation produces:

- **Unreachable targets** — the seam can't dispatch to Codex/Graphify.
- **Proxy distortion** — "documentation → Gemini" encodes a guess, not the
  actual routing intent.
- **Layer leakage** — provider-selection logic starts carrying task semantics it
  can't fully express, and every new task-type bloats the wrong component.

Separating the layers keeps each one's vocabulary honest: the Workflow Router
speaks *agents*, the Provider Router speaks *capabilities*.

## 2. Responsibilities

### 2.1 What the Workflow Router OWNS

| Responsibility | Concretely |
|---|---|
| **Task-type classification** | Map an incoming unit of work to a `WorkflowCategory` (§3) from explicit, deterministic signals — the invoked command/skill, file types touched, an explicit `--category` hint, the caller's stated intent. |
| **Target selection** | From the category, pick the target (§4) via the `Target` interface (§4a) — reading `can_handle(category)` and `available()`, honoring guardrails and fallback order. It **selects**; it does not `invoke` (that is the dispatcher's job — §2a). |
| **Guardrail enforcement** | The non-negotiable boundaries, evaluated *independent of the target registry* (F8): consulting-domain work → StratAgent's governed agents only (ADR-010 §6c); secrets/auth → gated (Engineering-Workflow.md). |
| **Loop prevention (marker)** | Stamp the `RoutingContext` (§6a) with `classified=true` + a dispatch-depth counter so re-entrant sub-work is not re-routed and cannot loop. |
| **Fallback selection** | On unknown/ambiguous input, choose the safe default target (§7). |
| **Observability** | One record per decision: matched category, selected target, reason, fallback status, `trace_id` — the same lightweight shape ADR-012 §12 uses, correlated across layers (§6a). |

### 2.2 What it explicitly does NOT own

- **Dispatch / invocation** — the router outputs a **decision** (`selected_target`);
  the **host (Claude Flow) calls `target.invoke(...)`** (§2a). The router never
  invokes a target itself.
- **Provider/model selection** — that is ADR-012's Provider Router, invoked *by
  the chosen agent* when it makes an LLM call. The Workflow Router never
  constructs a `TaskDescriptor` and never names a provider.
- **Doing the work / consulting judgment** — it routes to the agent that reasons;
  it does not reason about the business problem itself.
- **Arithmetic / quantitative verification** — the Quant Gate (ADR-009) still
  runs downstream regardless of which agent drafted.
- **Credentials** — it never holds keys or authenticates.
- **Being a failure domain** — if it errors or can't classify, it selects a safe
  default target (§7); it never blocks a unit of work.

## 2a. The classifier-vs-dispatcher decision (F2)

The review flagged that Claude Flow **already** owns agent dispatch and swarm
coordination (`agent_spawn`, `coordination_orchestrate`, `task_assign`,
`hooks_model-route`). Building a second dispatcher would duplicate it. Two
options:

| | **Option A — classifier + selector** *(chosen)* | **Option B — classify + dispatch** |
|---|---|---|
| Router does | classify → select target → emit decision | classify → select → **invoke** the target |
| Dispatch owned by | **Claude Flow** (existing coordination) | the router (Claude Flow demoted to infra) |
| Router shape | **pure function** (no side effects, no orchestration state) | stateful orchestrator |
| Duplicates Claude Flow? | No — feeds it | Yes — reimplements dispatch |
| Failure domain | none (pure) | a new orchestration failure domain |
| Testability / reversibility | trivial (classify in isolation) | harder (owns execution) |
| Cost | must define the router→host decision handoff | must reimplement coordination the host already has |

**Decision: Option A.** The Workflow Router is a **classifier + selector that
emits a `WorkflowDecision`**; **Claude Flow (the host) dispatches** by calling
`target.invoke(...)`. Rationale: it keeps the router a pure, deterministic,
independently-testable function — the exact property that made ADR-012's Provider
Router safe — and it *reuses* Claude Flow's orchestration instead of rebuilding
it. The router decides **who**; the host performs the call; the target does the
work. This is the responsibility split all of §2 now reflects.

The `WorkflowDecision` the router emits: `(category, selected_target,
fallback_targets, guardrail_verdict, routing_context, reason)`. The host reads
`selected_target` and invokes it via the §4a interface, walking
`fallback_targets` if it is unavailable.

## 3. Routing taxonomy — and why these are workflow categories

Each category names a **kind of work**, whose right owner is an *agent/toolchain*
— not a property of a single prompt. None is decidable from "does this call carry
an image / exceed a context window / need JSON" (the Provider Router's whole
vocabulary), which is exactly what makes them workflow-level.

| Category | What it is | Why it's workflow-level (not a provider capability) |
|---|---|---|
| **Coding** | Implement/refactor/scaffold code | Routes to a *code agent* (Codex/Claude Code); "which model" is a downstream, separate decision |
| **Debugging** | Root-cause a failing test/behavior | Needs an agent with repro tooling + repo context, not a model flag |
| **Code review** | Adversarial review of a diff | Needs an *independent* agent (a different model family than the author) — a governance choice, not a capability |
| **Documentation** | ADRs, READMEs, doc generation | Targets Claude Code (domain) / Codex (mechanical) — dev-stack tools, unreachable from the provider seam (the reverted-rule lesson) |
| **Repository analysis** | Structural/graph queries over the codebase | Routes to an *agent* (Claude/Codex) that **uses Graphify's tools** — Graphify is a capability the agent holds, not a target (§4a, F4), and certainly not a provider family |
| **Research** | Web/literature investigation | Needs an agent with WebSearch/WebFetch tools; the *tools*, not the model, define it |
| **Business consulting** | Run an engagement on a client problem | Routes to StratAgent's governed `solve-case` pipeline — the one category that reaches the product runtime; consulting judgment is agent work, never a dev tool |
| **General reasoning** | Anything not matched above | The safe-default catch-all → the primary always-available agent (Claude) |

**The through-line:** every category answers "which *actor* should own this,"
whose targets are agents and toolchains. Provider capabilities (vision,
long-context, JSON, cost, latency) are what that actor's individual LLM calls
then negotiate with ADR-012 — a strictly downstream, per-call concern.

## 4. Routing targets and the category → target map

Targets are agents/toolchains, deliberately **not** enumerated inside the router
as a hardcoded switch (§8) but declared in a table the router reads.

| Category | Primary target | Secondary / fallback | Context |
|---|---|---|---|
| Coding | **Codex** (mechanical/scaffolding) | Claude Code (domain-touching) | Engineering |
| Debugging | **Codex** (`/codex:rescue`, isolated repro) | Claude Code (cross-file/domain) | Engineering |
| Code review | **Codex** (independent adversarial) | Claude Code | Engineering |
| Documentation | **Claude Code** (ADR/architecture-linked) | Codex (mechanical doc sync) | Engineering |
| Repository analysis | **Claude/Codex, *using* Graphify tools** | Claude Code alone (no graph) | Engineering |
| Research | **Claude Code** (+ WebSearch/WebFetch) | *(future) research agent*; Gemini large-context (once adopted, ADR-010 §6d) | Engineering |
| Business consulting | **StratAgent `solve-case` agents** (governed) | *(future) consulting sub-agents* | **Product** |
| General reasoning | **Claude** (primary, always available) | — | Both |

Every "primary/secondary" entry is a **target** (an agent/toolchain that can own
a unit of work). **Graphify is not in this list** — it is a *tool* an agent uses
(F4), listed in that target's `describe().tools`, never selected directly.

**Extensibility of the map (§8):** the map is *data*. Adding a target =
registering a `Target` (§4a) — `(name, categories it can own, invocation)`;
adding a category = a new row + a classifier signal. No existing branch changes.

## 4a. The `Target` interface (F1)

Every selectable target — however heterogeneous its mechanism — satisfies one
minimal contract. This is the keystone the original draft left implicit; it is
what lets the router *select* uniformly and the host *invoke* uniformly over
wildly different underlying tools.

| Method | Purpose | Used by |
|---|---|---|
| `can_handle(category) -> bool` | Does this target own this workflow category? | Router (selection) |
| `available() -> bool` | Is it usable now (installed, authenticated, reachable)? | Router (selection + fallback) |
| `invoke(work, context) -> Result` | Perform the unit of work; `context` is the `RoutingContext` (§6a). | **Host / dispatcher** (not the router) |
| `describe() -> TargetInfo` | Static metadata: `name`, `kind`, `categories`, `tools` (e.g. Graphify), for logging/registry. | Router + observability |

**What is standardized:** the four-method signature, the `WorkflowCategory`
enum, and the `RoutingContext` shape passed to `invoke`. Selection logic depends
*only* on `can_handle` / `available` / `describe` — so the router is agnostic to
how any target actually runs.

**What stays implementation-specific:** the body of `invoke` and `available`.
Each target *kind* implements them differently:

| Target kind | `available()` | `invoke(work, context)` |
|---|---|---|
| **Claude session** | always `true` (primary) | continue in-session, or spawn a sub-agent, forwarding `context` |
| **Codex** | CLI installed + authenticated (`/codex:setup` state) | run the Codex command (`/codex:review`, `/codex:rescue`, …) as a subprocess; pass `context` as an argument |
| **Repository analysis (Claude/Codex *using* Graphify)** | the agent is available **and** Graphify MCP is reachable | the agent runs, calling Graphify's `query_graph`/`get_node` **as tools within its work** — Graphify is not invoked as a target |
| **Consulting skill (`solve-case`)** | always `true` (governed agents are in-repo) | run the `solve-case` skill/pipeline, forwarding `context` |
| **Future agents** | agent-defined | agent-defined — the only requirement is implementing these four methods |

Because Graphify only ever appears *inside* a target's `invoke` (as a tool it
calls), it never receives a `RoutingContext` of its own and never re-enters the
router — which also closes one recursion path (§6a).

## 5. Decision flow

### 5.1 Full stack (architecture)

```
User request / unit of work
    │
    ▼
┌────────────────────────────────────────────────────────────┐
│ WORKFLOW ROUTER  (this ADR — CLASSIFIER + SELECTOR, pure)   │
│   classify task-type → guardrails → select target           │
│   out: WorkflowDecision(category, selected_target, …)       │
└────────────────────────────────────────────────────────────┘
    │  decision (NOT an invocation)
    ▼
┌────────────────────────────────────────────────────────────┐
│ HOST / DISPATCHER  (Claude Flow — existing coordination)    │
│   target.invoke(work, RoutingContext)  · walks fallbacks    │
└────────────────────────────────────────────────────────────┘
    │
    ▼
Selected Target   (Codex · Claude · solve-case · Claude+Graphify-tools · …)
    │   the target does the work; when it makes an LLM call ↓
    ▼
┌────────────────────────────────────────────────────────────┐
│ PROVIDER ROUTER  (ADR-012)                                  │
│   capability of ONE prompt → provider-family ordering       │
└────────────────────────────────────────────────────────────┘
    │
    ▼
Provider selection (failover) ──▶ Model
```

(Graphify is not a layer here — it is a tool the "Claude+Graphify-tools" target
calls *inside* its work, per §4a.)

### 5.2 Sequence — an engineering task (e.g. "refactor this module")

```
User     WorkflowRouter      Host(ClaudeFlow)    Codex(target)     ProviderRouter   Model
 │ request   │                    │                 │                 │             │
 │──────────▶│ classify=coding    │                 │                 │             │
 │           │ guardrail ok       │                 │                 │             │
 │           │ decision──────────▶│ target.invoke() │                 │             │
 │           │ (selected=Codex)   │────────────────▶│ (does refactor) │             │
 │           │                    │                 │ LLM call───────▶│ cap. route  │
 │           │                    │                 │                 │────────────▶│
 │           │                    │                 │◀────────────────│ result      │
 │◀──────────│◀───────────────────│◀────────────────│ result          │             │
```

### 5.3 Sequence — a product consulting request (reaches the runtime)

```
User     WorkflowRouter      Host(ClaudeFlow)   solve-case agents   ProviderRouter  Model
 │ case      │                    │                 │                 │             │
 │──────────▶│ classify=consulting│                 │                 │             │
 │           │ guardrail: MUST be │                 │                 │             │
 │           │ governed agents    │                 │                 │             │
 │           │ decision──────────▶│ target.invoke() │                 │             │
 │           │ (selected=solve-   │────────────────▶│ classify→analyze│             │
 │           │  case)             │                 │ →challenge→report│            │
 │           │                    │                 │ each LLM call──▶│ cap. route   │
 │           │                    │                 │                 │────────────▶│
 │◀──────────│◀───────────────────│◀────────────────│ report          │             │
```

**The handoffs are one-directional and clean:** the Workflow Router emits a
*decision*; the host *invokes* the selected target; the target's LLM calls are the
Provider Router's input. No layer reaches back into the one above it.

## 6. Integration with ADR-012

| Aspect | Specification |
|---|---|
| **Inputs (Workflow Router)** | A unit of work (§6a) + classification signals: invoked command/skill, explicit `--category`, files/paths touched, stated intent. **Not** an LLM prompt. |
| **Outputs (Workflow Router)** | A `WorkflowDecision(category, selected_target, fallback_targets, guardrail_verdict, routing_context, reason)` — consumed by the **host** (§2a). **Never** a `TaskDescriptor`, never a provider name, never an `invoke`. |
| **Inputs (Provider Router, ADR-012)** | A `TaskDescriptor` for one LLM call, constructed **by the selected target** at call time (`agent_name`, `has_images`, `prompt_size`, `needs_json`), carrying the `trace_id` from `RoutingContext` for cross-layer correlation (F7). |
| **Boundary** | The selected target is the seam. Above it: task-type + target (this ADR). Below it: capability + provider (ADR-012). The target's identity + `trace_id` are the only things that cross down. |
| **Ownership** | Workflow Router owns classification + selection + guardrails. **The host owns dispatch** (§2a). Provider Router owns capability matching + provider ordering + failover. None imports another. |
| **No change to ADR-012** | The Provider Router already works standalone (P0–P3 shipped). This ADR sits above it and requires **zero** change to it — a target that exists today already funnels its calls through `call_with_failover` → the Provider Router. |

## 6a. Unit of work, RoutingContext, and recursion prevention (F3)

**A unit of work** is *one top-level request entering a routing context* — a
single Claude Code command/skill invocation, or a single dashboard engagement
request. It is **not** every sub-call, tool call, or analyst dispatch inside the
work. Classification happens **once**, at the unit's entry.

**What triggers routing (per context):**

| Context | Trigger (entry point) |
|---|---|
| Engineering (Claude Code) | a command/skill invocation at session entry (a hook or a thin front-skill), before any agent runs |
| Product (dashboard) | the engagement request boundary — the point that today invokes `solve-case` |

**Routing lifetime.** The `WorkflowDecision` is fixed for the unit's duration:
one classification, one selected target (plus fallbacks), held until the unit
completes. Sub-work does not re-classify.

**RoutingContext (where routing state lives).** State lives in an explicit
`RoutingContext` value threaded through `invoke` — **never a global**:

```
RoutingContext {
  trace_id: str          # correlates Workflow → Provider (ADR-012 §12) → event log
  category: WorkflowCategory
  classified: bool = true # idempotency marker
  dispatch_depth: int     # incremented per nested unit; hard-capped
}
```

**How it crosses boundaries** (the propagation mechanism the review found
missing):

| Boundary | Propagation |
|---|---|
| **Claude** (in-session / sub-agent) | `RoutingContext` rides in the agent/tool context; a spawned sub-agent inherits it |
| **Codex** (subprocess) | passed as an argument/env to the Codex invocation; Codex returns a result and **does not call back** into the router |
| **MCP tools (e.g. Graphify)** | tool calls happen *inside* a target's work and are **not** units of work — they receive no `RoutingContext` and never route |
| **Future agents** | must accept and forward `RoutingContext` — a requirement of the §4a `Target` contract |

**Recursion prevention.** Two guards, both in `RoutingContext`:
1. **Idempotency:** any work already carrying `classified=true` is **not
   re-classified** — it runs under its existing decision.
2. **Depth cap:** a genuinely new nested unit increments `dispatch_depth`; above a
   hard cap the router refuses to start a new unit and runs the work under the
   current target. Combined with "MCP tools aren't units" and "Codex doesn't call
   back," the re-entry paths are closed by construction.

## 7. Failure handling

| Case | Behavior |
|---|---|
| **Unknown task type** | No classifier signal matches → dispatch to the **General reasoning** default target (Claude, always available). Logged `status=fallback`. The work is never blocked. |
| **Ambiguous request** (two categories plausible) | Deterministic tie-break by a fixed category priority order (e.g. consulting-guardrail > review > coding > general); the losing category is recorded in the reason. If still unresolved and the signal is genuinely thin, degrade to General reasoning rather than guess. |
| **Selected target unavailable** (`available()` false — Codex unauthenticated/rate-limited) | The host walks `fallback_targets` (§2a), then Claude — the same fail-open discipline as ADR-012, unchanged from Engineering-Workflow.md's "Codex absent → Claude." |
| **A target's tool is down** (e.g. Graphify unreachable for repo-analysis) | Not a target failure — the target is still `available()`; it runs **without that tool** (repo-analysis → Claude alone, no graph), degrading gracefully. |
| **Classifier raises** | Fail-open: swallow, log, select the default target (mirrors ADR-012's `route()` guard). Routing is never a new failure domain. |
| **Consulting guardrail cannot be satisfied** (no governed agent available) | This is the one *hard* stop — consulting work must **not** silently fall to a dev tool (ADR-010 §6c). Surface an explicit error rather than misroute. |

## 8. Extensibility — add a category or target without touching existing logic

The router is **table-driven**, mirroring ADR-012's registry-driven design:

1. **New target:** register a `Target` (§4a) implementing the four-method
   interface. It becomes eligible for the categories its `can_handle` returns —
   no router branch edited, and the host invokes it through the same interface.
2. **New category:** add a row to the category→target map + one classifier signal
   (a command name, a path pattern, an explicit hint). Existing categories are
   untouched; first-match/priority ordering absorbs it.
3. **Classifier strategy is pluggable:** the rule-based classifier (§11) is one
   implementation behind a `classify(work) -> WorkflowCategory` interface; a
   future LLM classifier can replace it without changing selection, targets, or
   guardrails.
4. **Guardrails are evaluated independent of the target registry (F8).** A
   newly-registered `Target` whose `can_handle` claims the `consulting` category
   can **not** thereby bypass the "consulting → governed agents only" guardrail:
   guardrails run *before* and *independent of* target selection, against an
   explicit allow-list. Registration cannot become a guardrail bypass.

This is the same "new provider = one registry entry, zero router change"
property ADR-012 delivered, lifted to the agent layer.

## 9. Migration plan (phased, design-first, reversible)

The three blocking findings are now resolved in the design (§2a, §4a, §6a), so
W0's exit criteria are concrete rather than open questions.

| Phase | Deliverable | Behavior change | Proof it's safe |
|---|---|---|---|
| **W0 — Contracts** | Ratify the resolved contracts: the `Target` interface (§4a), the `RoutingContext` + unit-of-work model (§6a), and the classifier-only / Claude-Flow-dispatches split (§2a). Write the `classify` + `select` + target-map interfaces against them. No routing yet. | None. | Contract review; no runtime change. |
| **W1 — Rule-based classifier + selector (no dispatch change)** | Deterministic classifier (command/skill, path patterns, `--category`) + selection over the target map + guardrails (independent of registry, F8) + fallback. Emits a `WorkflowDecision`; the host acts on it only when the signal is explicit — everything else → General reasoning (today's behavior). | Additive; unmatched work behaves exactly as today. | Golden classification cases; existing flows unchanged when no rule matches. |
| **W2 — Formalize the engineering matrix via `Target`s** | Implement `Target`s for Claude/Codex/consulting + repo-analysis (Claude/Codex using Graphify tools, F4); the host dispatches through the interface for coding/debug/review/repo-analysis/documentation, replacing Engineering-Workflow.md's *human-convention* matrix. | The team's dev dispatch becomes inspectable + logged instead of by-hand. | Parity: each category selects where the convention already says. |
| **W3 — Observability + guardrail/loop hardening** | Per-decision telemetry (category/target/reason/fallback + `trace_id` correlated to ADR-012, F7); consulting + secrets guardrails structural; `RoutingContext` depth-cap + idempotency guard live (§6a). | Full task-aware selection with an end-to-end audit trail. | Telemetry present + correlated; a consulting request can never select a dev tool (test); loop guard tested. |

Each phase defaults to the previous phase's behavior; "turn the Workflow Router
off" is always a config flip back to today's convention-based dispatch — never a
code rollback. **ML/LLM classification is explicitly out of W0–W3** (§11).

## 10. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **Task misclassification** | High | Rule-based, explicit signals first (command/skill/path/hint) — not inference; ambiguity resolves by fixed priority, then degrades to the safe default. Every dispatch is logged with its reason so a wrong route is visible and fixable. |
| **Overlapping workflows** (a task fits two categories) | Med | Deterministic category priority order + first-match; the consulting/secrets guardrails always win. The losing category is recorded, so overlaps are observable and the priorities tunable. |
| **Routing loops** (an agent re-enters the router, which re-routes, …) | High | Resolved by design (§6a): classify **once per top-level unit**; `RoutingContext` carries an idempotent `classified` marker + a depth cap; MCP tool calls aren't units; Codex doesn't call back. The re-entry paths are closed by construction. |
| **Orchestration complexity** | Med→Low | Resolved by Option A (§2a): the router is a **pure classify→select function** — no dispatch, no state machine, no orchestration owned here. Dispatch stays with Claude Flow, which already does it. The router decides *who*, not *how*. |
| **Guardrail bypass** (consulting work reaching a dev tool) | High | The consulting guardrail is a hard stop, not a preference; a governed-agent-unavailable case errors rather than misroutes (§7). |
| **Convention drift** (map disagrees with Engineering-Workflow.md) | Low | W2 makes the doc's matrix the router's source; the doc becomes descriptive of the router, not a parallel authority. |

## 11. Recommendation — rule-based first; defer ML/LLM classification

**Adopt a rule-based Workflow Router for W0–W3. Defer ML/LLM-based
classification.** Justification, consistent with every prior decision in this
program:

- **The signals are already explicit.** In practice a unit of work arrives with a
  strong deterministic signal — the invoked command/skill (`/codex:review`,
  `/solve-case`), the files touched, an explicit intent. Classifying that with
  rules is accurate, transparent, and free; an LLM classifier would add cost,
  latency, and non-determinism to route work that a lookup already routes
  correctly.
- **Determinism is a feature here.** Dispatch must be reproducible and auditable
  (the consulting guardrail especially). A rule table is inspectable; an LLM
  classifier's "why did it route here" is not.
- **It mirrors what already works.** ADR-012's Provider Router is deterministic
  rules over a capability registry; Engineering-Workflow.md's dispatch is already
  a human-run rule table. W1 just makes that table executable.
- **The upgrade path is preserved (§8.3).** `classify()` is an interface. If real
  usage shows genuinely ambiguous, signal-poor work that rules can't separate,
  an LLM classifier can slot in behind the same interface later — a
  data-justified upgrade, not a speculative default. That mirrors ADR-012's
  "defer scoring until telemetry justifies it" (P4).

**Do not** build LLM classification into W0–W3. Revisit only if post-W3 dispatch
telemetry shows a material rate of misclassified, signal-poor work.

## 12. Consequences

- **+** Task-type dispatch becomes a single, inspectable, logged decision instead
  of human convention — the gap ADR-012 explicitly left open (its §6.2 / Track B).
- **+** The provider seam stays clean: task-types can never leak back into it (the
  reverted-documentation-rule class of error becomes structurally impossible).
- **+** New agents/categories are data entries, not router edits (§8).
- **+** Zero change to ADR-012 or the shipped Provider Router.
- **−** Introduces a classifier + selector component and a router→host decision
  handoff; dispatch itself is reused from Claude Flow (§2a), not rebuilt.
- **−** Most value is in the engineering context; the product runtime only gains
  the consulting-guardrail formalization — real, but narrower than the dev-side
  benefit. Honestly scoped, not oversold.
- **−** Requires disciplined loop/guardrail handling (§10) that the Provider
  Router — a pure per-call function — never needed.

## 13. What I am asking to decide

1. **Accept the Workflow Router as the upper routing layer** (ADR-012 §6.2 / Track
   B), owning task-type classification + target **selection** (not dispatch),
   above the Provider Router.
2. **Ratify Option A** (§2a): the router is a classifier + selector; **Claude Flow
   remains the dispatcher**. *(Resolves F2 — previously W0's open question.)*
3. **Adopt the `Target` interface** (§4a) and the **unit-of-work / RoutingContext**
   model (§6a) as the design contracts W0 ratifies. *(Resolves F1, F3.)*
4. **Adopt the rule-based classifier** for W0–W3; defer ML/LLM classification (§11).
5. **Confirm the phase order** (W0→W3), each reversible to convention-based dispatch.
