---
id: it_supply_chain
type: issue_tree
title: Supply Chain Issue Tree
tags:
- issue-tree
- supply-chain
source: ADR-004 §4 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
---

# Supply Chain Issue Tree

**Domain.** [[domains/supply-chain]]

**Primary framework.** [[frameworks/scor-network-optimization]]

**Root question.** How do we cut cost while maintaining service and resilience?

## MECE Issue Tree

```
ROOT: How do we cut cost while maintaining service and resilience?
├─ **BRANCH** Plan (demand/supply alignment)?
│  └─ LEAF H: Demand forecast inaccuracy is driving excess inventory or stock-outs
│       → evidence: forecast accuracy (MAPE), S&OP process maturity [computed]
├─ **BRANCH** Source (procurement efficiency)?
│  ├─ LEAF H: Supplier pricing is above market rates in addressable categories
│       → evidence: spend cube vs. benchmarks [external_source]
│  └─ LEAF H: Supplier concentration creates material supply risk
│       → evidence: resilience mapping, Tier-1/2 concentration [client_fact]
├─ **BRANCH** Make (operations efficiency)?
│  └─ LEAF H: Manufacturing OEE is below benchmark, driving excess unit cost
│       → evidence: OEE by plant vs. peer benchmark [external_source]
├─ **BRANCH** Deliver (fulfilment cost)?
│  └─ LEAF H: Cost-to-serve is above benchmark in addressable channels
│       → evidence: cost-to-serve analysis by channel [computed]
├─ **BRANCH** Resilience sufficient?
│  └─ LEAF H: Single points of failure exist that are not mitigated
│       → evidence: resilience map, recovery time objectives [client_fact]
```

## Branching logic
Branches are MECE — complete and non-overlapping at each level.
Each leaf states a falsifiable hypothesis prioritized by impact × likelihood.
Evidence requirements are typed per ADR-002 (client_fact | external_source | computed).

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
