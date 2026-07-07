---
id: it_market_entry
type: issue_tree
title: Market Entry Issue Tree
tags:
- issue-tree
- market-entry
source: ADR-004 §4 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
---

# Market Entry Issue Tree

**Domain.** [[domains/market-entry]]

**Primary framework.** [[frameworks/market-attractiveness-right-to-win]]

**Root question.** Should we enter this market, and how?

## MECE Issue Tree

```
ROOT: Should we enter this market, and how?
├─ **BRANCH** Is the market attractive?
│  ├─ LEAF H: Market size and growth are sufficient to justify entry investment
│       → evidence: TAM/SAM sizing, growth rate [external_source]
│  └─ LEAF H: Structural profitability (Five Forces) supports long-run margin
│       → evidence: Porter's Five Forces assessment [external_source]
├─ **BRANCH** Do we have a right to win?
│  ├─ LEAF H: Our capabilities and assets transfer to this market
│       → evidence: capability fit assessment [client_fact]
│  └─ LEAF H: We can achieve a defensible position vs. incumbents
│       → evidence: competitive advantage analysis [external_source]
├─ **BRANCH** What is the best entry mode?
│  └─ LEAF H: Organic build is viable given timeline and capability gaps
│       → evidence: build vs. buy vs. partner option analysis [computed]
├─ **BRANCH** Do the economics work?
│  └─ LEAF H: Investment payback is achievable within the strategic horizon
│       → evidence: entry investment + revenue ramp model → payback, IRR [computed]
```

## Branching logic
Branches are MECE — complete and non-overlapping at each level.
Each leaf states a falsifiable hypothesis prioritized by impact × likelihood.
Evidence requirements are typed per ADR-002 (client_fact | external_source | computed).

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
