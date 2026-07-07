---
id: it_profitability
type: issue_tree
title: Profitability Issue Tree
tags:
- issue-tree
- profitability
source: ADR-004 §4 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
---

# Profitability Issue Tree

**Domain.** [[domains/profitability]]

**Primary framework.** [[frameworks/profit-tree]]

**Root question.** Why did profit move, and what do we do?

## MECE Issue Tree

```
ROOT: Why did profit move, and what do we do?
├─ **BRANCH** Revenue side?
│  ├─ LEAF H: Price erosion — discounting or mix shift to lower-price products
│       → evidence: price realization trend, mix analysis [computed]
│  └─ LEAF H: Volume decline — market share loss or softening demand
│       → evidence: volume by segment, market share index [client_fact]
├─ **BRANCH** Cost side?
│  ├─ LEAF H: COGS inflation — input price or labor cost increases
│       → evidence: unit cost trend by input [computed]
│  └─ LEAF H: Operating deleverage — fixed cost spreading over lower volume
│       → evidence: fixed-cost ratio vs. prior period [computed]
```

## Branching logic
Branches are MECE — complete and non-overlapping at each level.
Each leaf states a falsifiable hypothesis prioritized by impact × likelihood.
Evidence requirements are typed per ADR-002 (client_fact | external_source | computed).

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
