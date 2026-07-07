---
id: it_new_product
type: issue_tree
title: New Product Launch Issue Tree
tags:
- issue-tree
- new-product-launch
source: ADR-004 §4 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
---

# New Product Launch Issue Tree

**Domain.** [[domains/new-product-launch]]

**Primary framework.** [[frameworks/launch-economics-gtm]]

**Root question.** Should we launch this product, and how?

## MECE Issue Tree

```
ROOT: Should we launch this product, and how?
├─ **BRANCH** Is there real demand?
│  └─ LEAF H: A distinct customer segment has an unmet job-to-be-done and WTP
│       → evidence: JTBD research, WTP study [client_fact]
├─ **BRANCH** Is the competitive position defensible?
│  └─ LEAF H: Substitutes and competitors do not already satisfy this job adequately
│       → evidence: competitive landscape scan [external_source]
├─ **BRANCH** Do the unit economics work?
│  └─ LEAF H: Contribution margin is positive and breakeven volume is achievable
│       → evidence: unit economics model, cannibalization-adjusted NPV [computed]
├─ **BRANCH** Is the GTM plan credible?
│  └─ LEAF H: Channel and pricing choices are aligned to reach the target segment
│       → evidence: GTM plan, channel economics [client_fact]
```

## Branching logic
Branches are MECE — complete and non-overlapping at each level.
Each leaf states a falsifiable hypothesis prioritized by impact × likelihood.
Evidence requirements are typed per ADR-002 (client_fact | external_source | computed).

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
