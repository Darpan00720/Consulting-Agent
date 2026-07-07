---
id: fw_resilience_map
type: framework
title: Supply Chain Resilience Mapping
tags:
- framework
- supporting
source: ADR-004 §3 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
name: Supply Chain Resilience Mapping
domains:
- '[[domains/supply-chain]]'
tier: supporting
purpose: Identify single points of failure, supplier concentration risks, and disruption
  scenarios in the supply network.
when_to_use: When supply chain risk has materialized or when redesigning the network
  for greater robustness.
diagnostic_questions:
- Where are single-source or geographically concentrated supplier risks?
- What is the business impact (revenue at risk, recovery time) of a disruption at
  each node?
success_metrics:
- Supplier concentration score by category
- Recovery time objective by critical node
common_risks:
- Building resilience at a cost that exceeds the expected value of disruption prevented
common_mistakes:
- Mapping only Tier-1 suppliers, missing Tier-2 and Tier-3 concentration risk
related_frameworks:
- '[[frameworks/scor-network-optimization]]'
version: '0.1'
---

# Supply Chain Resilience Mapping

**Domain(s).** [[domains/supply-chain]]

**Purpose.** Identify single points of failure, supplier concentration risks, and disruption scenarios in the supply network.

**When to use.** When supply chain risk has materialized or when redesigning the network for greater robustness.

## Diagnostic questions
- Where are single-source or geographically concentrated supplier risks?
- What is the business impact (revenue at risk, recovery time) of a disruption at each node?

## Success metrics
- Supplier concentration score by category
- Recovery time objective by critical node

## Common risks
- Building resilience at a cost that exceeds the expected value of disruption prevented

## Common mistakes
- Mapping only Tier-1 suppliers, missing Tier-2 and Tier-3 concentration risk

## Related frameworks
- [[frameworks/scor-network-optimization]]

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
