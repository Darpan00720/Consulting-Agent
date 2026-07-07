---
id: it_ai_strategy
type: issue_tree
title: AI Strategy Issue Tree
tags:
- issue-tree
- ai-strategy
source: ADR-004 §4 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
---

# AI Strategy Issue Tree

**Domain.** [[domains/ai-strategy]]

**Primary framework.** [[frameworks/ai-use-case-portfolio]]

**Root question.** Where should we apply AI, and how?

## MECE Issue Tree

```
ROOT: Where should we apply AI, and how?
├─ **BRANCH** Where does AI create value?
│  └─ LEAF H: Specific business processes have high AI value potential (cost, revenue, experience)
│       → evidence: AI value mapping by use case [computed]
├─ **BRANCH** Is it technically feasible?
│  ├─ LEAF H: Data is available, clean, and sufficient to train or fine-tune models
│       → evidence: data readiness assessment by use case [client_fact]
│  └─ LEAF H: Capability exists or can be sourced (build/buy/partner) within the horizon
│       → evidence: capability assessment, build/buy/partner analysis [client_fact]
├─ **BRANCH** Is data readiness sufficient?
│  └─ LEAF H: Data infrastructure gaps will delay or block high-priority use cases
│       → evidence: data maturity assessment, pipeline audit [client_fact]
├─ **BRANCH** Is governance in place?
│  └─ LEAF H: Responsible AI and regulatory compliance risks are not yet managed
│       → evidence: responsible-AI risk assessment, regulatory inventory [client_fact]
```

## Branching logic
Branches are MECE — complete and non-overlapping at each level.
Each leaf states a falsifiable hypothesis prioritized by impact × likelihood.
Evidence requirements are typed per ADR-002 (client_fact | external_source | computed).

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
