---
id: it_corporate_strategy
type: issue_tree
title: Corporate Strategy Issue Tree
tags:
- issue-tree
- corporate-strategy
source: ADR-004 §4 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
---

# Corporate Strategy Issue Tree

**Domain.** [[domains/corporate-strategy]]

**Primary framework.** [[frameworks/playing-to-win]]

**Root question.** Where do we play and how do we win at the portfolio level?

## MECE Issue Tree

```
ROOT: Where do we play and how do we win at the portfolio level?
├─ **BRANCH** Where to play?
│  └─ LEAF H: Current market/segment selection does not maximize long-run value creation
│       → evidence: portfolio economics by business unit [computed]
├─ **BRANCH** How to win?
│  └─ LEAF H: Competitive advantage is not clearly defined or is eroding
│       → evidence: right-to-win assessment, competitive positioning [external_source]
├─ **BRANCH** Is the portfolio balanced?
│  └─ LEAF H: Portfolio lacks balance across growth horizons (over-invested in H1, under in H2/H3)
│       → evidence: Three Horizons investment analysis [computed]
├─ **BRANCH** Is capital allocated to the best opportunities?
│  └─ LEAF H: Capital allocation does not match strategic priorities
│       → evidence: capital allocation framework vs. strategic choices [computed]
```

## Branching logic
Branches are MECE — complete and non-overlapping at each level.
Each leaf states a falsifiable hypothesis prioritized by impact × likelihood.
Evidence requirements are typed per ADR-002 (client_fact | external_source | computed).

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
