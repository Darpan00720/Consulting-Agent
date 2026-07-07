---
id: it_pricing
type: issue_tree
title: Pricing Issue Tree
tags:
- issue-tree
- pricing
source: ADR-004 §4 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
---

# Pricing Issue Tree

**Domain.** [[domains/pricing]]

**Primary framework.** [[frameworks/value-based-pricing]]

**Root question.** Are we capturing the right price?

## MECE Issue Tree

```
ROOT: Are we capturing the right price?
├─ **BRANCH** Is the price level right (value ceiling)?
│  └─ LEAF H: WTP is above current price — value-based headroom exists
│       → evidence: conjoint/Van Westendorp WTP analysis [client_fact]
├─ **BRANCH** Is the cost floor being respected?
│  └─ LEAF H: Some SKUs or contracts are priced below fully-loaded cost
│       → evidence: pocket price waterfall analysis [computed]
├─ **BRANCH** Is the competitive context factored in?
│  └─ LEAF H: Price is out of line with competitive alternatives customers consider
│       → evidence: competitor price comparison [external_source]
├─ **BRANCH** Is the price structure capturing value (structure)?
│  ├─ LEAF H: Significant price leakage occurs through discounts, terms, exceptions
│       → evidence: waterfall from list to pocket price [computed]
│  └─ LEAF H: Single price leaves money on table across segments with different WTP
│       → evidence: segmented WTP distribution [computed]
```

## Branching logic
Branches are MECE — complete and non-overlapping at each level.
Each leaf states a falsifiable hypothesis prioritized by impact × likelihood.
Evidence requirements are typed per ADR-002 (client_fact | external_source | computed).

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
