---
adr: 005
title: Agent Specifications
status: Proposed
date: 2026-06-30
deciders: [Product Owner, Principal AI Architect]
relates: [ADR-001 §6 Agents, ADR-002 Engagement State, ADR-003 Knowledge, ADR-004 Knowledge Library]
tags: [agents, contracts, interfaces, specifications]
---

# ADR-005 — Agent Specifications

> **Status:** Proposed (final architecture document before implementation)
> **Scope:** The definitive **contract** for every agent — responsibilities,
> boundaries, inputs, outputs, state interactions, pre/postconditions.
> **Out of scope (by instruction):** implementation, prompts, runtime workflows.
> **Framework-agnostic:** these contracts must hold under *any* orchestration
> mechanism. The ADR-001 binding (Ruflo swarm coordination + a host Task tool) is
> one valid implementation; nothing here may depend on it. Where this document
> says "the orchestration layer dispatches," it names a *role*, not a mechanism.

This ADR specifies the 16 agents of ADR-001 §6. State references use the section
names of ADR-002; knowledge dependencies reference the assets of ADR-004;
knowledge access obeys ADR-003.

---

# 1. Executive Summary

**Why agent behavior is separated from consulting knowledge.** Knowledge (what is
true and reusable — frameworks, KPIs, industries; ADR-004) is owned by the
consulting organization and versioned as assets. Behavior (how to reason, in what
order, to what standard — this ADR) is owned by engineering. Separating them means
a framework can be improved without redeploying an agent, an agent can be replaced
without rewriting consulting content, the same framework asset serves many agents,
and neither duplicates the other. Agents become thin, testable contracts over a
shared body of knowledge.

**Why agents are stateless except for the Engagement State.** Every agent is
defined as a contract: given a slice of the Engagement State (ADR-002), the
knowledge it depends on (ADR-004), and its inputs, it produces a defined set of
Engagement State writes and outputs — and holds **no private memory** between
invocations. This is what makes the system auditable (every effect is an event in
the state), replayable (re-running an agent on the same state slice yields the same
contract result), parallelizable (agents touching disjoint state sections cannot
conflict), resumable (no in-memory state to lose), and framework-agnostic (the
contract does not care how the agent was invoked). All shared memory lives in the
Engagement State; all firm memory lives in the knowledge layer. An agent that needs
hidden state is mis-specified.

---

# 2. Agent Taxonomy

Six categories, by role in an engagement.

| Category | Agents | Why the category exists |
|---|---|---|
| **Executive** | Engagement Manager | Someone must own the lifecycle, sequencing, gates, and escalation — the accountable "partner." Exactly one. |
| **Planning** | Case Classifier, Information Gap Agent, Planner, Framework Selector, Issue Tree Generator | Scope and *structure* the engagement before any analysis. Errors here are the cheapest to fix and the most expensive to miss. |
| **Knowledge** | Knowledge Agent, Knowledge Curator | The only agents permitted to touch firm knowledge — one reads (inbound), one writes-back (outbound). They enforce the ADR-003 boundary. |
| **Analysis** | Financial, Market, Operations, Strategy, Risk Analysts | Domain specialists producing evidence-backed findings on owned issue-tree branches. Independent and parallelizable. |
| **Governance** | Reviewer, Challenger | Independent QA and adversarial stress-test. Separation of duties: a producer never approves its own output. |
| **Reporting** | Executive Report Writer | Synthesis into the executive deliverable — a distinct skill from analysis, isolated so synthesis can't quietly redo analysis. |

---

# 3. Agent Specifications

Each agent below specifies all 13 contract fields. State names are ADR-002
sections; knowledge deps are ADR-004 assets; Tools are *categories* (§6).

## Executive

**Engagement Manager** — *Executive*
- *Purpose:* own the engagement lifecycle and enforce gates.
- *Responsibilities:* sequence phases; dispatch agents; enforce mandatory gates + HITL; merge results; record transitions.
- *Inputs:* the engagement (raw problem) → *Outputs:* phase transitions, gate records, dispatch decisions.
- *Reads State:* all · *Writes State:* Engagement Metadata, Lifecycle Status, quality_gates, routing_log, Audit Trail.
- *Knowledge deps:* domain→expected-deliverables (to know what "done" means). *Tools:* State/Memory only.
- *Success:* every phase + both governance gates executed in order; engagement reaches completed. *Fails if:* a gate is skipped or bypassed.
- *Escalates if:* a gate fails repeatedly or HITL input is required → human.
- *Pre:* engagement created. *Post:* engagement in a terminal state (completed/failed) with a full audit trail.

## Planning

**Case Classifier** — *Planning*
- *Purpose:* name the case and extract the real question + known facts.
- *Responsibilities:* select archetype (primary + hybrid); state the real question; capture facts/objectives/constraints/stakeholders.
- *Inputs:* raw_input → *Outputs:* classification.
- *Reads State:* Problem Definition · *Writes State:* Problem Definition, Objectives, Constraints, Stakeholders, Case Classification, known_facts.
- *Knowledge deps:* Domain catalog. *Tools:* Knowledge Retrieval (via Knowledge Agent), State.
- *Success:* archetype = the actual decision. *Fails if:* classifies the symptom; invents facts.
- *Escalates if:* low-confidence/multi-archetype ambiguity → Manager (HITL confirm).
- *Pre:* raw_input present. *Post:* case_type + real_question set.

**Information Gap Agent** — *Planning*
- *Purpose:* surface load-bearing unknowns before analysis.
- *Responsibilities:* list only decisive gaps; recommend ask-vs-assume; seed assumptions.
- *Inputs:* classification + facts → *Outputs:* gap list.
- *Reads State:* Case Classification, known_facts · *Writes State:* Information Gaps, seed Assumption Ledger.
- *Knowledge deps:* domain required-inputs / typical-questions. *Tools:* Knowledge Retrieval (via KA), State.
- *Success:* every load-bearing gap surfaced. *Fails if:* lists trivia or misses a decisive gap.
- *Escalates if:* a load-bearing gap cannot be safely assumed → human.
- *Pre:* case_type set. *Post:* all load-bearing gaps recorded (open/asked/assumed).

**Planner** — *Planning*
- *Purpose:* produce an executable engagement plan.
- *Responsibilities:* derive steps, dependencies, sequencing; identify parallelizable work.
- *Inputs:* gaps + archetype → *Outputs:* plan.
- *Reads State:* Case Classification, Information Gaps · *Writes State:* Engagement Plan.
- *Knowledge deps:* framework steps, domain expected deliverables. *Tools:* Knowledge Retrieval (via KA), State.
- *Success:* dependency-correct, executable plan. *Fails if:* unsequenced or assigns work no agent can do.
- *Escalates if:* the case is unanswerable without more input → Manager.
- *Pre:* load-bearing gaps resolved/assumed. *Post:* a plan with explicit parallel vs blocking steps.

**Framework Selector** — *Planning*
- *Purpose:* choose and adapt the framework(s).
- *Responsibilities:* select primary/supporting frameworks; justify; state adaptation.
- *Inputs:* archetype + question → *Outputs:* framework selection.
- *Reads State:* Case Classification, real_question · *Writes State:* Framework Selection.
- *Knowledge deps:* Framework library (ADR-004 §3). *Tools:* Knowledge Retrieval (via KA), State.
- *Success:* frameworks fit; adaptation explicit; "when-not-to-use" respected. *Fails if:* recites a non-fitting template.
- *Escalates if:* no framework fits → Manager (fall back to generic + flag).
- *Pre:* case_type + real_question set. *Post:* ≥1 framework selected with rationale.

**Issue Tree Generator** — *Planning*
- *Purpose:* build the MECE issue tree.
- *Responsibilities:* decompose the question into owned, testable sub-questions with evidence requirements.
- *Inputs:* frameworks + question → *Outputs:* issue tree.
- *Reads State:* Framework Selection, real_question · *Writes State:* Issue Tree.
- *Knowledge deps:* Issue Tree library + frameworks (ADR-004 §4). *Tools:* Knowledge Retrieval (via KA), State.
- *Success:* MECE; every leaf testable + has an evidence requirement. *Fails if:* overlaps, gaps, or topic-labels.
- *Escalates if:* the question resists a MECE decomposition → Manager.
- *Pre:* frameworks selected. *Post:* a validated MECE tree (per ADR-004 §4 rules).

## Knowledge

**Knowledge Agent** — *Knowledge*
- *Purpose:* the sole reader of firm knowledge on behalf of an engagement.
- *Responsibilities:* hybrid retrieval; rank; tenant-filter; provenance-tag; write results to state.
- *Inputs:* an analytical need (tree node/query), client, tenant → *Outputs:* knowledge references + evidence.
- *Reads State:* Issue Tree, client · *Writes State:* Knowledge References, Evidence Ledger (type=external_source).
- *Knowledge deps:* the entire library (frameworks, KPIs, industries, prior cases, playbooks). *Tools:* Knowledge Retrieval (graph+vector), Web Research, State.
- *Success:* relevant, tenant-legal, fully sourced (pinned to a knowledge version). *Fails if:* returns cross-tenant or un-sourced items.
- *Escalates if:* only cross-tenant matches exist, or nothing relevant is found → Manager (never leak, never fabricate).
- *Pre:* an issue tree or explicit query exists. *Post:* provenance-tagged references written; no un-sourced result.

**Knowledge Curator** — *Knowledge*
- *Purpose:* the sole writer-back of firm knowledge after an engagement.
- *Responsibilities:* distill lessons; create sanitized prior-case notes; update profiles; enforce provenance + tenant sanitization.
- *Inputs:* completed Engagement State → *Outputs:* knowledge contributions (firm knowledge) + Knowledge Links.
- *Reads State:* full completed state · *Writes State:* Knowledge Links (only); *writes firm knowledge* (Obsidian, outside the Engagement State).
- *Knowledge deps:* the entire library + governance rules (ADR-004 §9). *Tools:* Knowledge Retrieval, Knowledge Write, State.
- *Success:* a reusable, sourced lesson captured; correct graph placement; zero cross-tenant leakage. *Fails if:* writes un-sourced or leaks tenant data.
- *Escalates if:* a contribution would leak tenant data or lacks a source → steward.
- *Pre:* engagement completed. *Post:* firm knowledge updated via a reviewed, sanitized contribution.

## Analysis

*(All analysts share a contract shape: take owned issue-tree node(s) + facts, produce evidence-backed findings with labeled assumptions, sensitivity, and confidence. They obtain firm knowledge via the Knowledge Agent / Knowledge References — never directly.)*

**Financial Analyst** — *Analysis*
- *Purpose:* answer financial branches quantitatively.
- *Responsibilities:* P&L bridges, unit economics, valuation, breakeven, sensitivity.
- *Inputs:* owned nodes + facts → *Outputs:* financial findings.
- *Reads State:* Issue Tree, known_facts, Assumption Ledger, Knowledge References · *Writes State:* Financial Analysis, Evidence (computed), Assumption Ledger, Issue Tree node answers.
- *Knowledge deps:* KPI library (financial), framework methods. *Tools:* Compute, Spreadsheet/Modeling, State.
- *Success:* math traceable + sensitized; assumptions labeled with breakevens. *Fails if:* presents assumptions as facts or omits sensitivity.
- *Escalates if:* required inputs missing and not safely assumable → Manager.
- *Pre:* assigned node(s) + plan. *Post:* node(s) answered with computed evidence + confidence.

**Market Analyst** — *Analysis*
- *Purpose:* answer demand-side branches.
- *Responsibilities:* sizing (TAM/SAM/SOM), competitive dynamics, segments, WTP.
- *Inputs:* owned nodes + facts → *Outputs:* market findings.
- *Reads State:* Issue Tree, known_facts, Knowledge References · *Writes State:* Market Analysis, Evidence, Assumption Ledger, node answers.
- *Knowledge deps:* Industry model, market/entry frameworks, market-share KPI. *Tools:* Web Research, Compute, State.
- *Success:* sizing method stated; benchmarks labeled. *Fails if:* fabricates a citation or conflates "big" with "winnable."
- *Escalates if:* external evidence is unavailable/unreliable → Manager (fall back to labeled assumptions).
- *Pre:* assigned node(s). *Post:* node(s) answered with sourced evidence + confidence.

**Operations Analyst** — *Analysis*
- *Purpose:* answer cost/operations branches.
- *Responsibilities:* cost-to-serve, capacity, process, supply chain; one-time vs run-rate; second-order effects.
- *Inputs:* owned nodes + facts → *Outputs:* operations findings.
- *Reads State:* Issue Tree, known_facts, Knowledge References · *Writes State:* Operations Analysis, Evidence, Assumption Ledger, node answers.
- *Knowledge deps:* supply-chain/cost frameworks, ops KPIs, Industry model. *Tools:* Compute, Spreadsheet/Modeling, State.
- *Success:* cost decomposed before cuts; trade-offs flagged. *Fails if:* recommends cuts without stating what they risk.
- *Escalates if:* required operational data missing → Manager.
- *Pre:* assigned node(s). *Post:* node(s) answered with evidence + confidence.

**Strategy Analyst** — *Analysis*
- *Purpose:* answer positioning/options branches.
- *Responsibilities:* strategic options + trade-offs, entry mode, build/buy/partner, vs next-best alternative.
- *Inputs:* owned nodes + facts → *Outputs:* strategy findings.
- *Reads State:* Issue Tree, Knowledge References · *Writes State:* Strategy Analysis, Evidence, Assumption Ledger, node answers.
- *Knowledge deps:* corporate/strategy frameworks, Industry model. *Tools:* Web Research, State.
- *Success:* options compared against the next-best alternative. *Fails if:* asserts "strategic fit" with no quantified case.
- *Escalates if:* options cannot be evaluated without missing inputs → Manager.
- *Pre:* assigned node(s). *Post:* node(s) answered with evidence + confidence.

**Risk Analyst** — *Analysis*
- *Purpose:* answer downside/feasibility branches.
- *Responsibilities:* risk register (likelihood × impact), mitigations, competitive response.
- *Inputs:* findings so far → *Outputs:* risk findings.
- *Reads State:* Issue Tree, specialist findings, Assumption Ledger · *Writes State:* Risk Analysis, Evidence, node answers.
- *Knowledge deps:* risk patterns, PE-DD risk lens, industry regulatory. *Tools:* Compute, Web Research, State.
- *Success:* top risks quantified + mitigated. *Fails if:* generic risk list with no impact sizing.
- *Escalates if:* a risk is severe enough to threaten the recommendation → Manager/Challenger.
- *Pre:* at least one analysis finding exists. *Post:* a quantified, mitigated risk register.

## Governance

**Reviewer** — *Governance*
- *Purpose:* the analysis-quality gate.
- *Responsibilities:* MECE coverage, evidence traceability, internal consistency, confidence calibration, gap closure; validate evidence.
- *Inputs:* full analysis state → *Outputs:* review verdict + issues.
- *Reads State:* all analysis sections + ledgers · *Writes State:* Reviewer Notes, Evidence.validated, quality_gates.
- *Knowledge deps:* issue-tree validation rules, framework "common mistakes/when-not-to-use," KPI definitions. *Tools:* Compute (recompute), State.
- *Success:* no unsupported claim or contradiction passes. *Fails if:* rubber-stamps or misses an unanswered branch.
- *Escalates if:* needs_rework persists beyond bounded loops → human.
- *Pre:* every leaf answered; findings carry evidence. *Post:* verdict ∈ {approved, needs_rework} recorded.

**Challenger** — *Governance*
- *Purpose:* the recommendation stress-test gate.
- *Responsibilities:* load-bearing assumption test; strongest counter-case; what-would-change.
- *Inputs:* full state → *Outputs:* challenge verdict.
- *Reads State:* all · *Writes State:* Challenge Notes, quality_gates, may emit AssumptionInvalidated.
- *Knowledge deps:* framework "common risks," prior cases (counter-evidence). *Tools:* Compute, State.
- *Success:* a real counter-argument constructed or the recommendation verified. *Fails if:* manufactures a weak objection or softens findings.
- *Escalates if:* the recommendation fails repeatedly → human.
- *Pre:* Reviewer verdict = approved. *Post:* verdict ∈ {stands, stands_with_caveats, needs_rework} recorded.

## Reporting

**Executive Report Writer** — *Reporting*
- *Purpose:* synthesize the executive deliverable.
- *Responsibilities:* answer-first synthesis; preserve assumption labels; produce report/deck/model.
- *Inputs:* validated + challenged state → *Outputs:* recommendation + deliverables.
- *Reads State:* all · *Writes State:* Recommendations, Confidence Scores, Deliverables.
- *Knowledge deps:* Deliverable library + templates (ADR-004 §7). *Tools:* Document Generation, Spreadsheet, State.
- *Success:* top-down readable; decision unambiguous; assumptions visible. *Fails if:* upgrades an assumption to a fact for smoothness.
- *Escalates if:* both gates have not passed → refuses and escalates to Manager.
- *Pre:* Reviewer approved AND Challenger cleared. *Post:* recommendation + deliverables produced; ledgers preserved.

---

# 4. Collaboration Model

Collaboration is expressed as **contracts and dependencies**, never as a procedure.
(No runtime workflow here; the lifecycle sequence lives in ADR-002 §State Lifecycle.)

- **Sequential work** arises only from *state dependencies*: an agent whose
  preconditions require another agent's postconditions runs after it (e.g., Issue
  Tree Generator requires Framework Selection's output). Order is implied by
  pre/postconditions, not hardcoded.
- **Parallel work** is permitted whenever agents write **disjoint** state sections
  (ADR-002 owner-exclusive writes). Analysts on different issue-tree branches are
  inherently parallel; this is safe *because* agents are stateless and writes are
  section-scoped.
- **Review gates** are blocking contracts: the Reviewer's `approved` postcondition
  is a precondition of the Challenger; both are preconditions of the Report Writer.
- **Approval gates** enforce separation of duties: an agent may not satisfy its own
  approval precondition. Final acceptance is a human/Manager contract (ADR-002).
- **Knowledge retrieval** is mediated: any agent needing firm knowledge declares a
  dependency satisfied *through the Knowledge Agent* (or by reading Knowledge
  References in state) — never by direct vault/graph access (§7).
- **Conflict resolution** happens in the Engagement State, not between agents:
  contradictory findings are detected by the Reviewer's consistency check and must
  be *reconciled* (re-dispatch the implicated analyst), never averaged. Agents do
  not negotiate with each other.

---

# 5. Agent Contracts

Every agent conforms to one **standard contract**. This is the normative interface.

| Contract element | Requirement |
|---|---|
| **Required Inputs** | The exact Engagement State slice + knowledge dependencies the agent needs; missing inputs ⇒ the agent does not run (precondition unmet). |
| **Expected Outputs** | A declared, typed set of Engagement State writes (its owned sections) + a status. Nothing outside its owned sections. |
| **State Changes** | Expressed as appends/updates to owned sections only; emitted as events (ADR-002). No mutation of other agents' sections; no deletes. |
| **Validation Rules** | Every write must satisfy ADR-002 invariants (evidence typed + sourced; load-bearing assumptions have breakevens; issue-tree leaves testable). Invalid writes are rejected, not coerced. |
| **Failure Modes** | Declared, typed: missing-input, low-confidence, contradiction, no-knowledge, gate-fail. Failure is a recorded outcome, not a crash. |
| **Retry Rules** | Retries must be **idempotent** (safe to re-run on the same state slice — guaranteed by statelessness + event sourcing); bounded (max attempts), then escalate. |
| **Confidence Requirements** | Findings and recommendations carry an explicit confidence (0–1) with a stated basis; confidence ≤ min of supporting validated evidence (ADR-002 invariant). |
| **Evidence Requirements** | Every claim an agent writes declares an evidence type (client_fact / external_source / computed / assumption) with a source/method. No un-sourced claim is a valid output. |

These elements are uniform so any agent — current or future (§9) — is interchangeable
at the contract boundary regardless of how it is implemented.

---

# 6. Tool Contracts

Tools are referenced by **category**, not implementation (current bindings live in
ADR-001 §7 / ADR-003). `State/Memory` access is universal and omitted from the
matrix. Firm-knowledge access (`Knowledge Retrieval`, `Knowledge Write`) is
restricted to the Knowledge category by §7.

| Agent | Compute | Web Research | Knowledge Retrieval | Spreadsheet/Modeling | Doc Generation | Knowledge Write |
|---|---|---|---|---|---|---|
| Engagement Manager | — | — | — | — | — | — |
| Case Classifier | — | — | via KA | — | — | — |
| Information Gap Agent | — | — | via KA | — | — | — |
| Planner | — | — | via KA | — | — | — |
| Framework Selector | — | — | via KA | — | — | — |
| Issue Tree Generator | — | — | via KA | — | — | — |
| Knowledge Agent | — | ✓ | ✓ (direct) | — | — | — |
| Financial Analyst | ✓ | — | via KA | ✓ | — | — |
| Market Analyst | ✓ | ✓ | via KA | — | — | — |
| Operations Analyst | ✓ | — | via KA | ✓ | — | — |
| Strategy Analyst | — | ✓ | via KA | — | — | — |
| Risk Analyst | ✓ | ✓ | via KA | — | — | — |
| Reviewer | ✓ | — | via KA | — | — | — |
| Challenger | ✓ | — | via KA | — | — | — |
| Executive Report Writer | — | — | via KA | ✓ | ✓ | — |
| Knowledge Curator | — | — | ✓ (direct) | — | — | ✓ |

"via KA" = the agent may *consume* firm knowledge only through the Knowledge Agent
(or Knowledge References already in state), never directly. Only the Knowledge
Agent and Curator hold direct firm-knowledge access.

---

# 7. Knowledge Contracts

How agents interact with each knowledge component **without bypassing the
architecture** (ADR-003):

| Component | Who may interact | Contract |
|---|---|---|
| **Knowledge Agent** | All agents (as requesters) | Agents needing firm knowledge request it from the Knowledge Agent or read the Knowledge References it wrote to state. It is the single inbound gateway. |
| **Knowledge Curator** | Engagement Manager (triggers post-engagement) | The single outbound gateway; promotes engagement learnings to firm knowledge. No engagement-time agent invokes it mid-engagement. |
| **Obsidian (vault)** | Knowledge Agent (read), Curator (write) **only** | The authoritative firm-knowledge store. No other agent reads or writes it. Agents never treat the derived graph as the editable source. |
| **Graphify (graph+index)** | Knowledge Agent **only** (query) | Queried solely by the Knowledge Agent. Derived and rebuildable; never authoritative for edits; never queried directly by analysts. |
| **Ruflo Memory (Engagement State)** | **All agents** | The one shared channel. Every agent reads/writes per the ADR-002 R/W matrix. This is the *only* permitted inter-agent communication path. |

**Invariant:** the only inter-agent channel is the Engagement State; the only firm-
knowledge channels are the Knowledge Agent (in) and Curator (out). Any design that
has an analyst reading Obsidian/Graphify directly, or two agents messaging outside
the state, violates this ADR.

---

# 8. Governance

- **Ownership.** Each agent contract has a named engineering owner — distinct from
  the consulting stewards who own knowledge (ADR-004 §9). Behavior and knowledge are
  governed separately.
- **Versioning.** Agent contracts are semver-versioned. A change to required
  inputs, owned outputs, or pre/postconditions is **breaking** (major); internal
  behavior changes that preserve the contract are non-breaking.
- **Deprecation.** A contract is retired by a superseding contract; the engagement
  record notes which agent contract version produced each finding (auditability).
- **Testing.** Each agent is testable in isolation as a pure function of (state
  slice + knowledge + inputs) → (state writes + status); statelessness makes this
  deterministic. Contract-conformance tests assert pre/postconditions and that no
  out-of-scope section is written.
- **Evaluation.** Agents are evaluated against a consulting case-bank + rubric
  (a forthcoming ADR), including replay of engagement event logs; governance agents
  (Reviewer/Challenger) are held to a higher bar since they gate quality.
- **Approval.** A new or changed contract is reviewed and approved before the agent
  is admitted to the taxonomy — separate from knowledge-asset approval.

---

# 9. Future Evolution

New agents are introduced **without changing existing contracts** because every
agent communicates only through two stable surfaces: the Engagement State schema
(ADR-002) and the knowledge layer (ADR-003/004). To add an agent:

1. Place it in a taxonomy category (§2) — or propose a new category if it is a
   genuinely new role.
2. Declare its standard contract (§5): the state sections it reads, the **new or
   own** sections it writes (never another agent's), its knowledge dependencies,
   tool categories, and pre/postconditions.
3. If it produces a new kind of analysis, it writes a **new** Engagement State
   section (additive schema change) — existing agents are unaffected because writes
   are owner-exclusive and reads are tolerant of additive fields.

Because contracts are uniform and the only channels are the state and the knowledge
gateways, the system composes by **adding conforming contracts**, never by
rewiring existing ones. A new specialist (e.g., a Sustainability Analyst or a Legal
Analyst) slots into the Analysis category by declaring its branch ownership and
evidence requirements — no existing agent changes.

---

# Relationship to other ADRs
- **Specifies** the agents named in ADR-001 §6; **consumes** ADR-002 (state),
  ADR-003 (knowledge access), ADR-004 (knowledge assets).
- **Completes** the architecture phase. Implementation may begin on ratification,
  bound to a concrete orchestration mechanism (ADR-001's Ruflo binding or any other)
  without altering these contracts.
- **Forthcoming:** an evaluation-harness ADR (case-bank + rubric) referenced in §8.

---

*End of ADR-005. This document defines what each agent is accountable for and how it
interfaces — not how it is built. It must remain valid across any orchestration
framework.*
