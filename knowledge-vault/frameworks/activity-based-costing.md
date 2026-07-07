---
id: fw_abc_costing
type: framework
title: Activity-Based Costing (ABC)
tags:
- framework
- supporting
source: ADR-004 §3 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
name: Activity-Based Costing (ABC)
domains:
- '[[domains/cost-reduction]]'
tier: supporting
purpose: Assign costs to activities and products/services based on actual resource
  consumption, not volume-based allocation.
when_to_use: When traditional cost allocation obscures the true cost of serving different
  customers, products, or channels.
diagnostic_questions:
- Are high-volume products subsidizing low-volume complex ones?
- Do cost rates reflect actual resource consumption patterns?
success_metrics:
- True product/customer profitability
- Cost per unit of activity
common_risks:
- High implementation complexity and data requirements limiting adoption
common_mistakes:
- Using too many cost drivers, creating an unmanageable model
related_frameworks:
- '[[frameworks/cost-decomposition-benchmarking]]'
version: '0.1'
---

# Activity-Based Costing (ABC)

**Domain(s).** [[domains/cost-reduction]]

**Purpose.** Assign costs to activities and products/services based on actual resource consumption, not volume-based allocation.

**When to use.** When traditional cost allocation obscures the true cost of serving different customers, products, or channels.

## Diagnostic questions
- Are high-volume products subsidizing low-volume complex ones?
- Do cost rates reflect actual resource consumption patterns?

## Success metrics
- True product/customer profitability
- Cost per unit of activity

## Common risks
- High implementation complexity and data requirements limiting adoption

## Common mistakes
- Using too many cost drivers, creating an unmanageable model

## Related frameworks
- [[frameworks/cost-decomposition-benchmarking]]

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
