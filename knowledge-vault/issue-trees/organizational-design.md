---
id: it_org_design
type: issue_tree
title: Organizational Design Issue Tree
tags:
- issue-tree
- organizational-design
source: ADR-004 §4 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
---

# Organizational Design Issue Tree

**Domain.** [[domains/organizational-design]]

**Primary framework.** [[frameworks/operating-model-spans-layers]]

**Root question.** Is our organization fit for purpose?

## MECE Issue Tree

```
ROOT: Is our organization fit for purpose?
├─ **BRANCH** Is the structure aligned to strategy?
│  └─ LEAF H: Organizational structure groups conflicting priorities or separates related ones
│       → evidence: organizational design vs. strategy map [client_fact]
├─ **BRANCH** Are processes efficient?
│  └─ LEAF H: Core processes have excessive hand-offs or cycle times
│       → evidence: process cycle time analysis [client_fact]
├─ **BRANCH** Are decision rights clear?
│  └─ LEAF H: Key decisions are slow or frequently reversed due to unclear accountability
│       → evidence: decision-rights audit, escalation rate [client_fact]
├─ **BRANCH** Do people and capabilities match strategy?
│  └─ LEAF H: Critical capability gaps prevent strategy execution
│       → evidence: capability assessment vs. strategy requirements [client_fact]
```

## Branching logic
Branches are MECE — complete and non-overlapping at each level.
Each leaf states a falsifiable hypothesis prioritized by impact × likelihood.
Evidence requirements are typed per ADR-002 (client_fact | external_source | computed).

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
