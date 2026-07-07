---
id: it_pe_dd
type: issue_tree
title: PE Due Diligence Issue Tree
tags:
- issue-tree
- private-equity-due-diligence
source: ADR-004 §4 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
---

# PE Due Diligence Issue Tree

**Domain.** [[domains/private-equity-due-diligence]]

**Primary framework.** [[frameworks/commercial-dd-value-creation]]

**Root question.** Is the thesis real and is the deal value-creating?

## MECE Issue Tree

```
ROOT: Is the thesis real and is the deal value-creating?
├─ **BRANCH** Is the market attractive and growing?
│  └─ LEAF H: Market size, growth, and structural profitability support the thesis
│       → evidence: market/competitive analysis [external_source]
├─ **BRANCH** Is the competitive position durable?
│  └─ LEAF H: Market share and moats are real and defensible over the hold period
│       → evidence: market-competitive analysis, customer interviews [external_source]
├─ **BRANCH** Is the financial thesis valid?
│  ├─ LEAF H: EBITDA quality is high and sustainable — QoE supports the plan
│       → evidence: quality-of-earnings analysis [computed]
│  └─ LEAF H: Value-creation levers are specific and achievable in the hold period
│       → evidence: value-creation plan, management assessment [client_fact]
├─ **BRANCH** What is the value-creation plan?
│  └─ LEAF H: 100-day plan quick wins plus structural improvements drive EBITDA growth
│       → evidence: value-creation plan, 100-day priorities [computed]
├─ **BRANCH** Are risks acceptable?
│  └─ LEAF H: Key risks (market, operational, financial) are within the fund's risk appetite
│       → evidence: risk register, downside scenario model [computed]
```

## Branching logic
Branches are MECE — complete and non-overlapping at each level.
Each leaf states a falsifiable hypothesis prioritized by impact × likelihood.
Evidence requirements are typed per ADR-002 (client_fact | external_source | computed).

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
