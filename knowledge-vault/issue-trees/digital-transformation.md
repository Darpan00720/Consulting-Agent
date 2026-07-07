---
id: it_digital_transform
type: issue_tree
title: Digital Transformation Issue Tree
tags:
- issue-tree
- digital-transformation
source: ADR-004 §4 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
---

# Digital Transformation Issue Tree

**Domain.** [[domains/digital-transformation]]

**Primary framework.** [[frameworks/digital-maturity-value-feasibility]]

**Root question.** Where does digital create the most value, and what do we do first?

## MECE Issue Tree

```
ROOT: Where does digital create the most value, and what do we do first?
├─ **BRANCH** Where are the value pools?
│  └─ LEAF H: Specific value-chain steps have high digital value potential relative to baseline
│       → evidence: value-chain digitization assessment [computed]
├─ **BRANCH** Is it technically feasible?
│  └─ LEAF H: Data, technology, and talent are available or buildable within the horizon
│       → evidence: feasibility assessment by use case [client_fact]
├─ **BRANCH** Are capabilities and operating model ready?
│  └─ LEAF H: Capability gaps prevent delivery without structural operating model change
│       → evidence: capability audit, operating model assessment [client_fact]
```

## Branching logic
Branches are MECE — complete and non-overlapping at each level.
Each leaf states a falsifiable hypothesis prioritized by impact × likelihood.
Evidence requirements are typed per ADR-002 (client_fact | external_source | computed).

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
