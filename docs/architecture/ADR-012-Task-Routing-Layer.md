---
adr: 012
title: Task-Routing Layers — Workflow Router (task-type) and Provider Router (capability)
status: Accepted (Provider Router P0 registry + P1 identity + P2 vision + P3 capability-driven [vision/long-context/JSON] + routing telemetry implemented 2026-07-18; P4 scoring deferred)
date: 2026-07-18
deciders: [Principal Architect]
relates: [ADR-008 Repository Topology, ADR-009 Deterministic Quant Gate, ADR-010 Consulting Operating System, ADR-011 Consulting Quality Roadmap, ADR-014 Consulting Architecture Convergence]
supersedes: []
tags: [architecture, routing, providers, capability-matching, orchestration]
---

# ADR-012 — Intelligent Task-Routing Layer

> **Numbering note.** This task was briefed as "ADR-011," but `ADR-011`
> is already taken by *Consulting Quality Roadmap*
> ([ADR-011-Consulting-Quality-Roadmap.md](ADR-011-Consulting-Quality-Roadmap.md)),
> a separate design doc committed earlier. To avoid overwriting existing ADR
> history, this is filed as **ADR-012**. If the intent was to fold routing
> *into* ADR-011, that is a one-line rename — flagged rather than assumed.

> **Status:** Design document. P1 (identity router) is implemented; category
> rules are gated future work. Per this repo's design-first rule, provider code
> and failover are unchanged by design decisions recorded here.

> **Layer-separation correction (2026-07-18).** This ADR originally described a
> single "task router" and mixed two decisions that live at *different
> altitudes*: **task-type** routing (documentation, coding, research →
> agent/toolchain) and **capability** routing (vision, long-context → provider
> family). Attempting documentation routing at the provider seam exposed the
> conflation — its targets (Claude Code, Codex) aren't provider-chain families.
> This revision splits the design into two explicit layers — a **Workflow
> Router** (task-type, higher, *not built by this ADR*) and a **Provider
> Router** (capability, the seam this ADR builds) — moves each category to its
> layer, and makes **vision** (not documentation) the Provider Router's first
> real category. See §6 for the taxonomy and §13 for the corrected migration.
> **Implemented (2026-07-18):** the misplaced documentation rule was reverted
> and `_vision_rule` shipped as the Provider Router's first category.

---

## 1. The problem in one sentence

**Today the execution target is a function of provider *availability* only —
never of the *task*.** Every phase of an engagement — a two-token case
classification, a five-paragraph market summary, a 40-row quantitative ledger
reconcile, a final report render — is dispatched through the *same*
`call_with_failover()` against the *same* globally-ordered chain
(`gemini → cerebras → openrouter → github → cloudflare [→ ollama]`,
`providers.py:build_chain`). The chain reorders only for quota/cooldown
(`_ordered`), never for "what kind of work is this."

The consequences are concrete and already visible in this codebase:

- A trivial classification burns a scarce **Gemini** request (5 req/min per
  project) that a local **Ollama** model could have served for free.
- A dense reconcile prompt is sent to whichever provider is next in line, even
  though several (**GitHub Models** at 8k-in/4k-out, `_is_oversized`) *cannot
  physically serve it* — a wasted round-trip and a park.
- The one lever that exists — `OLLAMA_PLACEMENT=first|last` — is **global**:
  it forces *all* traffic local-first or *all* cloud-first. There is no way to
  say "classification local, strategy synthesis cloud-premium."
- The engineering stack (Claude / Codex / Ollama / Claude Flow MCP / Graphify
  MCP) picks its target *by human convention* (Engineering-Workflow.md), not by
  a shared, inspectable decision function.

The registry already anticipates the fix. `registry.py`'s own docstring: the
capability flags are *"the contract a future task-router would consume."* This
ADR designs that router.

## 2. Current architecture (as-is)

```
Request  (agent_name, system, user, max_tokens, byok?, images?)
    │
    ▼
call_with_failover()                       ← providers.py
    │   picks first AVAILABLE provider,
    │   fails over on 429 / 5xx / oversize,
    │   pauses+resumes on full rate-limit wall
    ▼
build_chain()  →  [ gemini, cerebras, openrouter, github, cloudflare, (ollama) ]
    │            (order = fixed quality/limit preference; task-blind)
    ▼
Provider.call()  →  one base_url + one model id (OpenAI-shaped transport)
    ▼
Model
```

- **`Provider`** is a transport: one `base_url`, one `model`, its own pacing
  (`min_gap`) and cooldown state. It has no cross-provider view.
- **`build_chain()`** encodes a *global preference ranking* by free-tier quality
  and limits. It is availability logic, not task logic.
- **`registry.ModelSpec`** already carries the capability flags a router needs
  (`supports_reasoning`, `supports_json`, `supports_vision`, `context_length`,
  `local`, …) but nothing routes on them yet — by design (registry.py note).
- **BYOK** bypasses the chain entirely to a single premium provider.

## 3. Desired architecture (to-be) — two routing layers

Routing happens at **two altitudes**. Keeping them separate is the whole point
of this revision.

```
Unit of work  (e.g. "write the ADR", "refactor this module", "answer this case")
    │
    ▼
┌──────────────────────────────────────────────────────────────────────┐
│ WORKFLOW ROUTER   (task-TYPE → agent / toolchain / model-family)       │
│   higher layer · orchestration-level · NOT built by this ADR           │
│   documentation→Claude/Codex · coding→Codex · repo-analysis→Graphify   │
│   research→Claude+web · consulting→StratAgent's governed agents ONLY   │
│   home: Claude Flow / engagement lifecycle / Engineering-Workflow.md   │
└──────────────────────────────────────────────────────────────────────┘
    │  the chosen agent issues LLM calls; EACH call then enters ↓
    ▼
┌──────────────────────────────────────────────────────────────────────┐
│ PROVIDER ROUTER   (capability of ONE prompt → provider-family order)   │
│   this ADR · the `call_with_failover` seam                             │
│   in:  TaskDescriptor + live signals + policy + registry               │
│   out: RoutingDecision  (ordered candidate families + constraints)     │
│   vision · long-context · reasoning · structured-JSON · local/cloud ·  │
│   latency · cost                                                       │
└──────────────────────────────────────────────────────────────────────┘
    │  RoutingDecision is an ORDERING/FILTER, not a new transport
    ▼
Provider selection  (existing failover honors the decision's order + constraints)
    │
    ▼
Model
```

**The dividing line:** a decision belongs to the **Provider Router** iff it can
be made from the *intrinsic properties of a single prompt* matched to a *model
capability* (does this call carry an image? exceed a context window? need
JSON?). A decision that requires knowing *what kind of work this is*
(documentation vs coding vs a consulting question) belongs to the **Workflow
Router** — a different component, at a different altitude, whose targets are
often not even provider-chain families.

Neither router replaces failover — the Provider Router *parametrizes* it.
Failover remains the safety net (cooldowns, resume-on-wall, all of §2
unchanged); the Provider Router changes *which families, in what order, under
what constraints* that loop is handed for a given call. An "identity" Provider
Router reproduces today's behavior exactly, which is what makes the migration
safe (§10). **This ADR designs and builds only the Provider Router;** the
Workflow Router is scoped here but deferred to its own home (§6.2, §13).

## 4. Where the router lives — the placement decision

| Option | Verdict | Why |
|---|---|---|
| **Inside `Provider`** | ✗ Rejected | A `Provider` is a single transport with no cross-provider view. Routing *is* a cross-target decision; it cannot live inside one target. |
| **Inside `build_chain()`** | ✗ Rejected | `build_chain` answers "who is available and in what quality order," a stable, task-independent concern. Injecting task classification couples two orthogonal responsibilities and makes the chain non-reusable across tasks. |
| **A heavy orchestration service** (à la Claude Flow) | ✗ Rejected | The router is a *pure function* of (task, capability registry, live health, policy) → decision. It holds no long-lived state, spawns nothing, owns no workflow. Making it a stateful service adds a failure domain for no gain. Claude Flow is a *consumer/peer* of the router (§7), not its host. |
| **A separate, thin decision module invoked at the call boundary, emitting a `RoutingDecision` the existing failover consumes** | ✓ **Recommended** | Keeps failover, pacing, and cooldown untouched. Reads the registry (capabilities) and live chain health (from `providers`), applies policy, returns an *ordered candidate list + constraints*. One seam: `call_with_failover` (or a thin wrapper) asks the router for the candidate ordering instead of using the fixed global one. Maximally additive; identity-router = today. |

**Decision: the router is a standalone `router` module that sits *before*
provider selection and produces a `RoutingDecision` consumed at the existing
call seam.** It is "before Provider" in the request flow, but it *reuses*
`build_chain()`'s providers and the failover loop rather than duplicating them.

## 5. Component responsibilities (Provider Router)

This section describes the **Provider Router** — the component this ADR builds.
The Workflow Router's responsibilities live in its own future home (§6.2, §13).

### 5.1 What the Provider Router owns

| Responsibility | What it means concretely |
|---|---|
| **Capability derivation** | Read the intrinsic requirements of the incoming call (`has_images`→`needs_vision`, `prompt_size`→`min_context`, caller-declared `needs_reasoning`/`needs_json`) from the `TaskDescriptor` already passed to `call_with_failover`, plus light prompt-shape features. It does **not** classify *task-type* — that is the Workflow Router's job (§6.2). No LLM call to route an LLM call. |
| **Capability matching** | Turn a category into hard *requirements* (`needs_vision`, `needs_reasoning`, `needs_json`, `min_context`, `determinism_class`) and match them against `registry.ModelSpec` flags. A target that cannot meet a hard requirement is filtered out *before* it wastes a failover round-trip (fixes the "send an 8k prompt to a 4k provider" waste). |
| **Latency awareness** | Prefer low-latency targets for interactive/short tasks; tolerate slow, high-quality targets for deep synthesis. Signal source: observed p50/p95 per provider from the existing telemetry layer (ADR: `telemetry/`), plus `min_gap` (a paced provider has higher effective latency). |
| **Cost awareness** | Prefer **free/local** (Ollama, `local=True`, cost 0) for low-stakes categories; allow **cloud free-tier** for the middle; reserve **BYOK premium** for high-stakes synthesis. Cost is a per-target scalar the scorer weights, not a hard gate (except a policy ceiling). |
| **Local-vs-cloud preference** | Generalize today's *global* `OLLAMA_PLACEMENT` into a *per-category* preference. Classification/extraction default local-first; strategy-synthesis/report default cloud-premium-first. The global knob becomes a policy default the per-category rules can override. |
| **Fallback strategy** | The `RoutingDecision` is an *ordered* candidate list, not a single pick — so "fallback" is just "the rest of the list," honored by the *existing* failover loop with its existing cooldown/resume semantics. The router decides the *order*; failover executes it. |
| **Confidence thresholds** | Each decision carries a `confidence`. Below a floor (ambiguous task, thin signal) the router degrades to the **safe default** (today's global chain) rather than making a risky specialized choice — the same "low confidence → fall back to the proven path" discipline the pipeline already uses elsewhere. |
| **Deterministic routing rules** | The non-negotiable guardrails (§6.4) are pure `if/else`, not scored: same inputs → same decision, always. Routing must be reproducible or it undermines engagement replayability (ADR-002/replay). |
| **Future extensibility** | New target ⇒ register a `ModelSpec` (+ a target adapter if it's not OpenAI-shaped). Capability matching makes it *automatically eligible* for any category whose requirements it meets — **no router code change** (§9). |

### 5.2 What the router does NOT own (hard boundaries)

- **It does not make consulting judgments.** Routing an LLM call is not the same
  as answering the business question. The consulting-domain boundary from
  ADR-010 §6c / Engineering-Workflow.md is unchanged: methodology stays with
  StratAgent's governed agents.
- **It does not verify arithmetic.** Quantitative *reasoning* may be routed, but
  the **Quant Gate (ADR-009) still runs, deterministically, on the output** no
  matter where it ran. The router picks who drafts; code still proves the math.
- **It does not build providers or hold keys.** It orders `Provider`s that
  `build_chain()` already built; credentials never pass through it.
- **It is not a new failure domain.** If the router errors or is disabled, the
  call falls straight through to today's fixed chain.

## 6. Routing taxonomy — two layers, two category families

The categories divide cleanly by the §3 dividing line. **Task-type** categories
are Workflow Router concerns; **capability** categories are Provider Router
concerns. The original ADR listed both under one router — that was the error.

### 6.1 The two layers, side by side

| | **Workflow Router** | **Provider Router** (this ADR) |
|---|---|---|
| **Decides** | Which agent / toolchain / model-family owns a unit of work | Which provider family serves one prompt |
| **Keys on** | Task *type* (a workflow judgment) | Capability *requirements* intrinsic to the prompt |
| **Targets** | Claude Code, Codex, Graphify, StratAgent's agents — often **not** provider-chain families | `gemini`, `cerebras`, `openrouter`, `github`, `cloudflare`, `ollama` |
| **Home** | Claude Flow / engagement lifecycle / Engineering-Workflow.md | `call_with_failover` seam |
| **Built here?** | **No** — scoped, deferred to its own ADR/home | **Yes** — P1 done, categories phased |

### 6.2 Workflow Router categories (task-type — higher layer, not built here)

These require knowing *what kind of work* a task is; their targets are agents
and dev-stack tools, not provider families, so they cannot be realized at the
provider seam. Listed for completeness and to fix their home — **out of scope
for this ADR's implementation.**

| Category | Target(s) | Rationale |
|---|---|---|
| **documentation** | Claude Code (ADR/architecture-linked) → Codex (mechanical doc sync) | Domain-linked docs need continuity; mechanical regeneration can be Codex. *(Moved here from the Provider Router — its targets aren't chain families.)* |
| **coding** | Codex (mechanical/scaffolding) → Claude Code (domain-touching) | Engineering-Workflow.md: Codex owns large mechanical refactors; Claude owns domain code. |
| **testing** | Codex (test scaffolding) → Claude Code | Deterministic-module tests still require the Codex adversarial gate + a passing regression test. |
| **repository analysis** | Graphify MCP (structural graph) + Claude (synthesis) | Graphify produces the AST/graph; workflow router directs structural queries there, synthesis to Claude. |
| **research** | Claude Code (WebSearch/WebFetch) → Gemini (large-context sweep, once/if adopted) | Judgment + web tools; Gemini is the designed-not-live tie-breaker (ADR-010 §6d). |
| **consulting** | **StratAgent's governed agents ONLY** — never a dev tool | The ADR-010 §6c hard boundary: methodology is the product's job, not a router's. |

### 6.3 Provider Router categories (capability — this ADR's router)

Each is decidable from the intrinsic shape of one prompt, matched to a
`registry.ModelSpec` capability flag. "Preferred" heads the ordered
`RoutingDecision`; the remainder is failover order. All are **preferences that
reorder/filter** — never a hard pick — so failover always remains the safety net.

| Category | Requirement (from the prompt) | Preferred families | Rationale |
|---|---|---|---|
| **vision / multimodal** | call carries images → `needs_vision` | `gemini`, `github` (gpt-4.1), local `gemma3` | Keep image-bearing calls on `supports_vision` providers. **Today a text-only landing silently drops the image and answers as if it weren't there** — this fixes a wrong-answer bug, not just an optimization. *(Recommended first category — §11.)* |
| **long-context** | `prompt_size` over a threshold → `min_context` | `gemini` (1M ctx), `cerebras`; **avoid** `github` (8k in/4k out) | Formalizes what `_is_oversized` handles reactively — steer big prompts away from providers that will 413. |
| **reasoning** | caller-declared `needs_reasoning` | `cerebras` gpt-oss, `gemini` flash, `openrouter` nemotron | Reasoning models exist in the chain; route deliberate-reasoning calls to them. Declared, not inferred. |
| **structured JSON** | `needs_json` | `supports_json` families: `ollama` qwen3, `gemini`, `github` | Structured output must land on a provider that reliably emits JSON. |
| **local/cloud preference** | stakes / cost policy | per-category local-first vs cloud-first | Generalizes today's *global* `OLLAMA_PLACEMENT` into a per-call preference. |
| **latency** | interactive vs deep-synthesis | low-`min_gap` / fast providers first | Short interactive calls prefer fast targets; deep synthesis tolerates slow-but-strong. |
| **cost** | stakes | free/local → cloud free-tier → BYOK premium | Reserve premium for high-stakes calls; keep low-stakes ones off scarce quota. |

### 6.4 Deterministic guardrails (hard boundaries, evaluated first in both layers)

These are pure `if/else`, never scored away. Each notes which layer enforces it:

1. **Consulting-domain reasoning → Claude/governed agents only** *(Workflow
   Router)* — never a dev tool or weak local model (ADR-010 §6c).
2. **Quantitative *values*/ledger arithmetic → deterministic services, not a
   model** *(cross-cutting)* — the LLM may draft; the Ledger Builder + Quant Gate
   (ADR-009/010) compute and verify.
3. **Secrets/auth → never a local or third-party model without the
   Engineering-Workflow.md gate** *(Workflow Router)*.
4. **BYOK present → honor it** *(Provider Router)* — premium single-target path,
   as today; the Provider Router does not reorder a one-provider chain.

> Categories are **not final** — they are the initial partition. New categories
> are additive within their layer: a category is a name + a requirement profile
> (Provider Router) or a target policy (Workflow Router) + a default ordering.

## 7. How the router interacts with the rest of the system

| Component | Interaction |
|---|---|
| **Provider abstraction** (`providers.py`) | Router *consumes* `Provider`s from `build_chain()`/`byok_provider()` and returns an ordering + constraints. It does **not** subclass, wrap, or replace `Provider`. The seam is `call_with_failover` asking the router for the candidate list instead of using the fixed global one. |
| **Registry** (`registry.py`) | Primary capability source — exactly the consumer the registry was built for. Router reads `ModelSpec` flags for capability matching. **Prerequisite:** the five cloud providers currently owned by `build_chain()` must be represented in the registry (Phase 0) so the router can reason about them, not just Ollama. |
| **Existing failover logic** | **Unchanged and still authoritative.** Cooldowns, `_ordered` intra-family key selection, `AllProvidersRateLimitedError` resume — all preserved. The router supplies a task-shaped candidate list; failover executes it with the same resilience it has today. If the router's preferred targets are all cooled, failover walks the rest exactly as now. |
| **Workflow Router** (future, §6.2) | The layer *above* the Provider Router. It picks the agent/toolchain for a unit of work; that agent then issues LLM calls, each of which enters the Provider Router. The two never merge: task-type decisions stay up top, capability decisions stay at the seam. This ADR builds only the lower layer. |
| **Claude Flow orchestration** | The natural **host of the Workflow Router**, and a peer (not host) of the Provider Router. Touch-points: (a) Claude Flow *dispatches* multi-agent work whose individual calls each pass through the Provider Router; (b) it exposes `hooks_model-route`/`hooks_model-outcome` — the Provider Router can *emit* outcome signals there and optionally *consult* recommendations as one input, without ceding the decision. |
| **Graphify** | A **Workflow Router** target (the repository-analysis task-type routes structural queries to Graphify's AST/graph) and a *signal source*. Not a provider-chain family, so it is *not* a Provider Router target — which is exactly why repo-analysis is a workflow, not a capability, category. No reverse coupling — Graphify does not depend on either router. |
| **Future providers** | The extensibility contract (§9): register a `ModelSpec`, provide a transport adapter if non-OpenAI-shaped, done. Capability matching makes it eligible automatically. No enumerated provider list in the router to edit. |

## 8. Provider Router decision flow

Upstream, the **Workflow Router** (§6.2) has already chosen the agent for this
unit of work; that agent's LLM call is what enters here. This flow is the
**Provider Router** only — capability requirements → provider-family ordering.

```
             ┌──────────────────────────── RoutingDecision ───────────────────────────┐
             │                                                                          │
LLM call ─▶ derive requirements ─▶ apply DETERMINISTIC GUARDRAILS (§6.4)                │
             (has_images,      │                                                         │
              size, declared)  ├─ guardrail fires? ─── yes ──▶ forced target set ───────▶├─▶ ordered
                              │                                (e.g. Claude-only)        │   candidates
                              no                                                         │   + constraints
                              │                                                          │        │
                              ▼                                                          │        ▼
                    build ELIGIBLE set:                                                  │  existing
                    filter chain by HARD requirements                                    │  failover loop
                    (needs_vision / needs_json / min_context / …)                        │  (unchanged:
                              │                                                          │   cooldown,
                              ▼                                                          │   resume,
                    SCORE eligible targets:                                              │   pacing)
                    w_cost·cost + w_lat·latency + w_quality·fit                          │        │
                    + w_local·local_pref  (per-category weights)                         │        ▼
                              │                                                          │      Model
                              ▼                                                          │
                    confidence < floor? ── yes ──▶ fall back to today's global chain ───▶│
                              │                                                          │
                              no ──▶ ordered candidate list (best score first) ─────────▶│
             └──────────────────────────────────────────────────────────────────────────┘
```

Every path exits to the **same** failover loop. The router only ever decides
*the candidate ordering and the hard filters*; it never executes a call, never
holds a key, and always has a safe fallback (the current global chain).

## 9. Future expansion — adding a provider with zero router changes

The design's central extensibility claim, made concrete:

1. **Register capabilities:** add a `ModelSpec` (or several) to the registry —
   `provider`, `model`, `context_length`, and the capability flags. This already
   works today (`registry.register`).
2. **Provide transport if needed:** if the provider is OpenAI-shaped (as Ollama,
   Gemini, Cerebras, OpenRouter, GitHub, Cloudflare all are), `Provider` already
   serves it — just an entry in `build_chain`. If it speaks a different protocol,
   add one adapter behind the `Provider.call` interface.
3. **Nothing else.** Capability matching (§5.1) makes the new target eligible for
   every category whose hard requirements it satisfies, and scoring ranks it by
   its declared cost/latency/quality. There is **no per-provider branch in the
   router to edit** — the router reasons over capabilities, not names.

This is the same pattern the registry's docstring already commits to, and the
reason capability-based matching (Option B, folded into the recommended hybrid)
is preferred over a hard-coded rule table.

## 10. Options evaluated & trade-offs

### Option A — Static rule-based routing
A fixed lookup table: `category → (provider, model, fallback…)`, hand-written.

- **+** Trivially deterministic, fully transparent, near-zero runtime cost.
- **+** Easiest to review; every route is visible in one table.
- **−** Brittle: every new provider/model needs a table edit in N categories.
- **−** No capability awareness — nothing stops the table from routing an 8k
  prompt to a 4k provider; correctness lives in the author's head.
- **−** No adaptivity: can't react to live latency, cost, or a provider having a
  bad day. Ignores the live-health machinery the chain already has.

### Option B — Capability-based routing
Router derives task *requirements*, matches them against `ModelSpec` flags +
live signals, and scores eligible targets to pick an order.

- **+** New providers auto-eligible (§9) — the extensibility goal, delivered.
- **+** Cannot misroute past a hard requirement (vision/context/json filtered).
- **+** Adaptive to cost/latency/health.
- **−** More moving parts; scoring weights need tuning and can produce
  *surprising* routes ("why did it pick X?").
- **−** Purely-scored routing risks eroding hard boundaries (e.g. cost pressure
  nudging a domain-reasoning task toward a cheap local model) unless guardrails
  are bolted on — which is exactly Option C.

### Option C — Hybrid (deterministic guardrails + capability scoring) ✅
Deterministic rules encode the non-negotiable boundaries **first** (§6.4);
capability matching + scoring choose **within** the allowed set; failover is the
final safety net; low confidence degrades to today's chain.

- **+** Safety of rules on the things that must never vary (consulting-domain →
  Claude, quant → deterministic gate, secrets → gated) **and** the adaptivity /
  extensibility of capabilities on the open-ended "which eligible target now."
- **+** Mirrors this codebase's own established philosophy exactly — deterministic
  guardrails with judgment inside them (P1/P2, the governance gates, the Quant
  Gate). It is the *same shape* the team already trusts.
- **+** Identity-configurable: with empty rules and flat weights it reproduces
  today's chain, making the migration provably safe (all existing tests pass).
- **−** Two mechanisms to understand (a rule pass and a scoring pass) — mitigated
  by ordering (rules always first) and by logging *why* each decision was made.

## 11. Recommendation

**Adopt Option C (Hybrid).** It is the only option that satisfies all seven
requirement themes at once — deterministic where the business demands it,
capability-driven where flexibility pays, extensible to new providers without
code change, and reproducible enough not to break engagement replay. It also
reuses, rather than replaces, the two proven assets already in the tree: the
failover loop (`providers.py`) and the capability registry (`registry.py`).

Concretely, the recommended shape is a `router` module returning a
`RoutingDecision` (ordered candidates + hard constraints + confidence +
rationale), consumed at the `call_with_failover` seam, defaulting to an identity
decision (today's chain) until each category is deliberately switched on.

**First category: vision** (§6.3, §13 P2). It is the cleanest capability fit —
`has_images` is intrinsic to the call and already flows into the
`TaskDescriptor`, `supports_vision` already exists and is already acted on, and
it fixes a real bug (a multimodal call landing on a text-only provider silently
drops the image). Task-type categories (documentation, coding, …) are **not**
Provider Router work — they belong to the Workflow Router (§6.2), a separate
future component.

## 12. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| **Misrouting a high-stakes task to a weak/local model** | High | Guardrails (§6.4) run first and cannot be scored away; consulting/high-stakes work is a Workflow-Router decision that never lands on a weak local model; confidence floor degrades to the safe chain. |
| **Router adds latency/complexity to a hot path** | Med | Routing is a pure, in-process function over cached registry + live counters — no network, no LLM call to route an LLM call. Budget: sub-millisecond. |
| **Capability flags drift from reality** (a model claims `supports_json` but doesn't) | Med | Flags are verified against real behavior on registration (same discipline as the Ollama entries, verified on-machine); the Quant Gate / schema validators still catch bad structured output downstream. |
| **Router becomes a hidden single point of failure** | High | It holds no state and owns no keys; on any router error the call falls through to today's fixed chain. Failover is unchanged and remains authoritative. |
| **Stale cost/latency signals cause thrashing** | Low | Signals are advisory (scoring weights), never hard gates; hysteresis/cooldown from the existing chain damps oscillation. |
| **Over-routing to Codex/Gemini increases external data-sharing** | Med | A **Workflow Router** concern (Codex/Gemini are its targets, not the Provider Router's); it honors the data-sharing gates already documented (ADR-010 §6c/§6d, Engineering-Workflow.md). Gemini remains not-wired-in until adopted. |
| **Non-determinism undermines replay** | High | The guardrail pass is pure `if/else`; scoring is deterministic given the same signal snapshot; the chosen `RoutingDecision` is logged with the engagement so a replay can pin the same route. |
| **Weight tuning turns into guesswork** | Low | Weights ship as one documented default (as the recommendation-ranker's did, ADR-010 §6b); tuned only against observed outcomes via the Claude Flow outcome hook, never by vibe. |

## 13. Migration plan (from the current architecture)

Two tracks now, because there are two routers. **Track A (Provider Router)** is
what this ADR builds and phases; **Track B (Workflow Router)** is scoped here but
deferred to its own home. Both are additive, gated, and reversible.

### 13.1 Track A — Provider Router (this ADR)

| Phase | Deliverable | Behavior change | Proof it's safe |
|---|---|---|---|
| **P0 — Registry completion** ✅ | DONE (2026-07-18). All five cloud providers now in `registry.py` with capability flags + a `max_request_tokens` tier-cap field; `model_supports()` / `effective_context()` capability-lookup helpers added. | None (declarative metadata + helpers; `build_chain` untouched). | 8 registry tests; full suite green. |
| **P1 — Identity router** ✅ | DONE (2026-07-18). `app/pipeline/router.py`: `TaskDescriptor`, `RoutingDecision`, a deterministic rule engine (`route`/`apply_decision`/`route_chain`) with an **empty production ruleset**, wired at the `call_with_failover` non-BYOK seam, fail-open on a raising rule. | **None** — empty ruleset ⇒ identity over the chain. | All existing provider tests pass unmodified; ruff clean. |
| **P2 — First capability category: VISION** ✅ | DONE (2026-07-18). `_vision_rule`: when `TaskDescriptor.has_images`, prefer providers whose model supports vision. Initially family-based; **refined in P3 to registry-driven** (below). Reorder-only, fail-open. | Image calls prefer providers that can read the image (correctness fix); text-only calls untouched. | Vision tests green. |
| **P3 — Capability-driven routing** ✅ | DONE (2026-07-18). `RoutingDecision` extended with `prefer_flags` + `min_context`; `apply_decision` resolves capabilities from the **registry** (`_provider_satisfies`, provider `.model` → `ModelSpec`), with a live-flag fallback for unregistered models. Vision now registry-driven (no family names; vision-capable `gemma3` auto-preferred, text-only `qwen3` not). **Long-context** (`_long_context_rule`, `min_context` vs `effective_context`, tier-cap aware) and **structured-JSON** (`_json_rule`, caller-declared `needs_json`) rules added. Seam passes an approx `prompt_size`. **Routing telemetry**: one DEBUG line per decision (matched capability / selected providers / reason / fallback status). | Image/large/JSON calls prefer capable providers; all reorder-only, fail-open, failover intact. Text-only small calls unchanged. | ~40 router + 8 registry tests; full backend suite 268 passed; my files ruff clean. |
| **P4 — Scoring for safe categories** | Capability scoring for low-stakes categories first (local/cloud + cost + latency). | Scarce cloud quota saved; high-stakes calls still identity-routed. | A/B on cost + latency telemetry vs. the identity baseline. |
| **P5 — Full capability matrix + outcome learning** | Enable the remaining §6.3 categories; feed outcomes to the Claude Flow hook to tune weights. | Full capability-aware routing. | Outcome metrics stay ≥ baseline; any regression reverts one category via policy. |

> **Correction to the earlier P2 (2026-07-18, resolved).** A previous P2 shipped
> `_documentation_rule` (a task-type category) at the provider seam, realized as
> a Gemini-for-prose preference. That was the layer conflation this revision
> fixes: documentation is a **Workflow Router** category (§6.2), not a Provider
> Router one. **Resolved:** `_documentation_rule` and its tests were reverted and
> replaced by `_vision_rule` (the corrected P2 above); `_RULES = [_vision_rule]`.

### 13.2 Track B — Workflow Router (separate, future — its own ADR)

Not built by this ADR. Today, task-type routing is governed by **human
convention** (Engineering-Workflow.md's Claude/Codex/Graphify matrix). Making it
a real, inspectable component is a distinct effort:

| Phase | Deliverable |
|---|---|
| **W0 — Home + ADR** | Decide the host (Claude Flow extension vs. a formalized Engineering-Workflow.md dispatcher) and write its own ADR. Its targets are agents/tools, not provider families. |
| **W1 — First task-type category** | E.g. documentation → Claude Code/Codex, or repo-analysis → Graphify, as an explicit dispatch rule rather than convention. |
| **W2+** | Remaining §6.2 categories; the `consulting` guardrail (§6.4.1) enforced structurally. |

Every phase in both tracks defaults to the previous phase's behavior, so "turn a
router off" is always a policy flip back to the proven path — never a code
rollback.

## 14. What I am asking to decide

1. **Accept the two-layer split** (§3, §6): a **Workflow Router** (task-type →
   agent/toolchain, deferred to its own home) above a **Provider Router**
   (capability → provider family, built here). This ADR builds only the latter.
2. **Accept the placement** (§4): the Provider Router is a standalone `router`
   module emitting a `RoutingDecision` consumed at the failover seam — *before*
   provider selection, *reusing* the chain and failover, not replacing them.
3. **Adopt Option C** (Hybrid: deterministic guardrails + capability scoring).
4. **Confirm the corrected phase order** (Track A P0→P5), with **vision** as the
   first category and the misplaced documentation rule reverted (§13.1).
5. **Confirm the ADR number** (012, because 011 is taken) — or request a merge.

## 15. Consequences

- **+** Task-aware execution: scarce cloud quota stops being spent on trivial
  work; incapable targets stop being tried on prompts they can't serve.
- **+** The *global* `OLLAMA_PLACEMENT` knob generalizes into per-category
  local-vs-cloud preference without breaking the global default.
- **+** New providers become a registry entry, not a router edit (§9).
- **+** Reuses the two proven assets (failover loop, capability registry) rather
  than re-deriving them; identity-router keeps the product bit-for-bit unchanged
  until each category is deliberately enabled.
- **−** Adds a decision layer to reason about and log; mitigated by rules-first
  ordering and per-decision rationale.
- **−** Real value only lands once categories are switched on (P4+); P1–P3 are
  safety scaffolding that, alone, change nothing a user sees.
- **−** Requires the registry retrofit (P0) that ADR-008/registry.py deliberately
  deferred — a prerequisite, not free.
