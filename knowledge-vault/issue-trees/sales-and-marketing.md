---
id: it_sales_marketing
type: issue_tree
title: Sales & Marketing Issue Tree
tags:
- issue-tree
- sales-and-marketing
source: ADR-004 §4 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
---

# Sales & Marketing Issue Tree

**Domain.** [[domains/sales-and-marketing]]

**Primary framework.** [[frameworks/funnel-gtm-economics]]

**Root question.** Where does the commercial engine leak, and how do we fix it?

## MECE Issue Tree

```
ROOT: Where does the commercial engine leak, and how do we fix it?
├─ **BRANCH** Where does the funnel leak?
│  ├─ LEAF H: Top-of-funnel conversion is low — awareness or lead quality is the constraint
│       → evidence: funnel stage conversion rates [computed]
│  └─ LEAF H: Bottom-of-funnel conversion is low — sales process or product is the constraint
│       → evidence: win/loss analysis, pipeline stage conversion [client_fact]
├─ **BRANCH** Are channel economics healthy?
│  └─ LEAF H: CAC:LTV is unfavorable in one or more key channels
│       → evidence: CAC/LTV by channel [computed]
├─ **BRANCH** Is sales productivity sufficient?
│  └─ LEAF H: Revenue per sales FTE is below benchmark due to process or enablement gaps
│       → evidence: quota attainment, revenue per FTE vs. peers [external_source]
```

## Branching logic
Branches are MECE — complete and non-overlapping at each level.
Each leaf states a falsifiable hypothesis prioritized by impact × likelihood.
Evidence requirements are typed per ADR-002 (client_fact | external_source | computed).

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
