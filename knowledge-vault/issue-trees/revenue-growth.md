---
id: it_revenue_growth
type: issue_tree
title: Revenue Growth Issue Tree
tags:
- issue-tree
- revenue-growth
source: ADR-004 §4 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
---

# Revenue Growth Issue Tree

**Domain.** [[domains/revenue-growth]]

**Primary framework.** [[frameworks/growth-driver-tree]]

**Root question.** How do we grow profitably?

## MECE Issue Tree

```
ROOT: How do we grow profitably?
├─ **BRANCH** Acquire more customers?
│  ├─ LEAF H: Market is underpenetrated — acquisition opportunity exists
│       → evidence: market share vs. TAM [external_source]
│  └─ LEAF H: CAC is too high relative to LTV — acquisition is uneconomical at current efficiency
│       → evidence: CAC trend, LTV:CAC ratio [computed]
├─ **BRANCH** Retain existing customers better?
│  └─ LEAF H: Churn is elevated — experience or product gaps are driving defection
│       → evidence: cohort churn rate, exit survey data [client_fact]
├─ **BRANCH** Expand revenue from existing customers?
│  └─ LEAF H: Share of wallet is low — upsell and cross-sell opportunities exist
│       → evidence: share-of-wallet estimate, attach rate [computed]
├─ **BRANCH** Enter new markets or launch new products?
│  └─ LEAF H: Adjacent market offers sufficient size and right-to-win
│       → evidence: TAM/SAM sizing, capability fit assessment [external_source]
```

## Branching logic
Branches are MECE — complete and non-overlapping at each level.
Each leaf states a falsifiable hypothesis prioritized by impact × likelihood.
Evidence requirements are typed per ADR-002 (client_fact | external_source | computed).

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
