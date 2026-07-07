---
id: it_manda
type: issue_tree
title: M&A Issue Tree
tags:
- issue-tree
- m-and-a
source: ADR-004 §4 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
---

# M&A Issue Tree

**Domain.** [[domains/m-and-a]]

**Primary framework.** [[frameworks/synergy-valuation]]

**Root question.** Should we buy this target, and at what price?

## MECE Issue Tree

```
ROOT: Should we buy this target, and at what price?
├─ **BRANCH** Is the strategic rationale sound?
│  └─ LEAF H: Acquisition fills a capability or market gap that would take longer to build organically
│       → evidence: strategic gap analysis [client_fact]
├─ **BRANCH** What is the standalone value?
│  └─ LEAF H: DCF and comps value is within a range that supports the investment
│       → evidence: DCF valuation, comparable multiples [computed]
├─ **BRANCH** Are synergies real and risk-adjusted?
│  ├─ LEAF H: Revenue synergies are credible and achievable within the horizon
│       → evidence: revenue synergy build-up, integration plan [computed]
│  └─ LEAF H: Cost synergies are specific and achievable within integration cost
│       → evidence: cost synergy build-up, integration cost [computed]
├─ **BRANCH** Is the integration risk manageable?
│  └─ LEAF H: Cultural and operational integration risk is within acceptable range
│       → evidence: integration risk assessment, PMI plan [client_fact]
```

## Branching logic
Branches are MECE — complete and non-overlapping at each level.
Each leaf states a falsifiable hypothesis prioritized by impact × likelihood.
Evidence requirements are typed per ADR-002 (client_fact | external_source | computed).

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
