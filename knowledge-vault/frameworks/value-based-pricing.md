---
id: fw_value_based_pricing
type: framework
title: Value-Based Pricing & Price Waterfall
tags:
- framework
- pricing
source: ADR-004 §3 (Consulting Knowledge Library)
last_verified: '2026-07-06'
status: draft
visibility: global
name: Value-Based Pricing & Price Waterfall
domains:
- '[[domains/pricing]]'
tier: primary
purpose: Set price between the value ceiling and cost floor, then choose level and
  structure; fix waterfall leakage.
when_to_use: Setting or fixing price level and structure.
diagnostic_questions:
- Is pricing cost-plus by default?
- Where is leakage in the price waterfall?
- What is the elasticity?
success_metrics:
- Pocket margin
- Price realization
- Attach rate
common_risks:
- Ignoring competitive response
common_mistakes:
- Cost-plus pricing without a value ceiling
related_frameworks: []
version: '0.1'
---

# Value-Based Pricing & Price Waterfall

**Domain.** [[domains/pricing]]

**Purpose.** Set price between the value ceiling and cost floor, then choose level and structure; fix waterfall leakage.

**When to use.** Setting or fixing price level and structure.
**When not to use.** Commodities with no pricing power.

## Logic
Objective → value ceiling → cost floor → competitive context → structure. Set the bounds, then choose level and structure.

## Diagnostic questions
- Is pricing cost-plus by default?
- Where is leakage in the price waterfall?
- What is the elasticity?

## Success metrics
- Pocket margin
- Price realization
- Attach rate

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
