---
adr: 007
title: Evidence Provider Extension Mechanism
status: Accepted
date: 2026-07-09
deciders: [Principal Architect]
relates: [ADR-002 §14 Evidence Ledger, ADR-003 §Knowledge (decision D-6), RC1 Validation Campaign]
tags: [evidence, providers, extension, knowledge, convergence]
---

# ADR-007 — Evidence Provider Extension Mechanism

> **Status:** Accepted (RC1.2 Architecture Convergence Sprint, WI-4).
> **Scope:** Defines the *extension mechanism* for attaching external-evidence
> providers. **No providers are populated** — this ADR and `packages/evidence/`
> ship the interface and machinery only.

---

## 1. Context

The RC1 Validation Campaign (finding **F-1**) confirmed that the knowledge vault
holds analytical frameworks but **no quantitative benchmarks** — market sizes,
comparables, KPI base rates. This is deliberate: ADR-003 decision **D-6** makes
benchmarks reviewer-supplied rather than baked into the vault. The consequence is
that every number in a pilot engagement was a *labeled assumption*; the system
reasons honestly but cannot ground a claim in sourced external data.

The convergence goal (WI-4) is **not** to invent benchmark data. It is to build
the sanctioned seam through which sourced evidence *may later* be attached,
without any agent fabricating numbers.

## 2. Decision

Introduce `packages/evidence/` — a provider extension mechanism with five parts.
Nothing in it performs I/O or ships a concrete provider.

### 2.1 Provider interface (`EvidenceProvider` Protocol)

A `runtime_checkable` Protocol: `provider_id`, `name`, `startup()`,
`health() -> ProviderStatus`, `fetch(ProviderQuery) -> Sequence[ProviderResult]`,
`shutdown()`. Structural typing means deployments implement it without importing
a base class.

### 2.2 Provenance-carrying results (`ProviderResult`)

Field names mirror `state.ledgers.Evidence` (`claim`, `source`, `confidence`,
`as_of`, plus `provider_id`, `value`, `url`, `raw`). `source` is **mandatory** —
a result with no citation is not evidence. This lets a caller promote a result
into the Evidence Ledger as an `EvidenceType.EXTERNAL_SOURCE` record (ADR-002
§14), which requires a source. **Traceability**: every result carries the
`provider_id` that produced it.

### 2.3 Lifecycle

`UNINITIALIZED → READY → (DEGRADED) → CLOSED`, plus `UNAVAILABLE`. The registry
drives `startup()`/`health()`/`shutdown()` and records status transitions.

### 2.4 Caching (`ProviderCache`)

A bounded TTL cache with deterministic keys (`cache_key(provider_id, query)`),
injectable monotonic clock (testable without sleeps), and oldest-first eviction.

### 2.5 Failure handling & isolation (`ProviderRegistry`)

The single consumption seam. `fetch()` fans a query out to registered providers
and returns a `FetchOutcome` (merged results + per-provider `errors` +
`from_cache` set + timestamp). Guarantees:

- **Isolation** — a provider that raises, times out, or is unavailable is
  recorded in `errors` and never breaks the others; healthy results still return.
- **Time budget** — each provider call runs under a hard timeout
  (`ThreadPoolExecutor` + `future.result(timeout=…)`); a breach becomes a
  `ProviderTimeoutError` and marks the provider `DEGRADED`.
- **Graceful degradation** — an empty registry (the default, since none are
  populated) simply returns no results; retrieval continues on the vault alone.

## 3. Integration seam (not activated)

The mechanism is standalone. A future deployment that attaches a provider would
have the Knowledge Agent (or retrieval layer) consult a `ProviderRegistry`
alongside the vault, then promote each `ProviderResult` into the Evidence Ledger
as an `external_source` record. RC1.2 does **not** wire this into
`knowledge.retrieval_adapter` — that module (frozen at M3) is untouched, and no
provider is registered anywhere.

## 4. Consequences

- Adds `packages/evidence/` (interface, cache, registry, errors). No changes to
  `state`, `persistence`, `replay`, `knowledge`, or `reporting`.
- The "empty evidence base" limitation (F-1) is now *addressable by
  configuration* rather than by code changes — a deployment attaches a provider;
  the platform never invents data.
- Because no provider is populated, engagement behaviour is unchanged from RC1.

## 5. Non-goals

- No concrete providers (web search, market-data vendors, benchmark DBs).
- No population of the vault with benchmark numbers.
- No change to how the vault itself is retrieved.
