---
id: it_customer_strategy
type: issue_tree
title: Customer Strategy Issue Tree
tags:
- issue-tree
- customer-strategy
source: ADR-004 §4 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
---

# Customer Strategy Issue Tree

**Domain.** [[domains/customer-strategy]]

**Primary framework.** [[frameworks/segmentation-clv]]

**Root question.** Which customers should we serve, and how do we keep them?

## MECE Issue Tree

```
ROOT: Which customers should we serve, and how do we keep them?
├─ **BRANCH** Which segments create the most value?
│  └─ LEAF H: Value (CLV) is concentrated in a small subset of segments
│       → evidence: CLV model by segment [computed]
├─ **BRANCH** Are high-value customers retained?
│  └─ LEAF H: Churn is disproportionately high among high-LTV customers
│       → evidence: churn rate by segment [computed]
├─ **BRANCH** Where does the journey break?
│  └─ LEAF H: Specific touchpoints drive dissatisfaction and defection
│       → evidence: journey mapping, NPS by touchpoint [client_fact]
├─ **BRANCH** What drives retention and expansion?
│  └─ LEAF H: Retention levers (engagement, product usage, service) are not optimized
│       → evidence: retention economics model, churn driver analysis [computed]
```

## Branching logic
Branches are MECE — complete and non-overlapping at each level.
Each leaf states a falsifiable hypothesis prioritized by impact × likelihood.
Evidence requirements are typed per ADR-002 (client_fact | external_source | computed).

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
