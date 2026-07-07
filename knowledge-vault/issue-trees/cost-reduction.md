---
id: it_cost_reduction
type: issue_tree
title: Cost Reduction Issue Tree
tags:
- issue-tree
- cost-reduction
source: ADR-004 §4 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
---

# Cost Reduction Issue Tree

**Domain.** [[domains/cost-reduction]]

**Primary framework.** [[frameworks/cost-decomposition-benchmarking]]

**Root question.** Where can we cut costs without harming operations?

## MECE Issue Tree

```
ROOT: Where can we cut costs without harming operations?
├─ **BRANCH** Quick-win opportunities?
│  ├─ LEAF H: Procurement spend is above market rate for addressable categories
│       → evidence: spend cube vs. benchmarks [external_source]
│  └─ LEAF H: Discretionary overhead is above peer benchmarks
│       → evidence: SG&A % vs. peer set [external_source]
├─ **BRANCH** Structural cost reduction?
│  ├─ LEAF H: Operating model has too many layers or duplicated roles
│       → evidence: spans-and-layers analysis [client_fact]
│  └─ LEAF H: Shared-service consolidation opportunity exists
│       → evidence: function headcount and process duplication [client_fact]
├─ **BRANCH** Strategic exit from activities?
│  └─ LEAF H: Non-core activities are consuming disproportionate cost
│       → evidence: activity-based cost allocation [computed]
```

## Branching logic
Branches are MECE — complete and non-overlapping at each level.
Each leaf states a falsifiable hypothesis prioritized by impact × likelihood.
Evidence requirements are typed per ADR-002 (client_fact | external_source | computed).

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
