---
id: fw_cost_to_serve
type: framework
title: Cost-to-Serve Analysis
tags:
- framework
- supporting
source: ADR-004 §3 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
name: Cost-to-Serve Analysis
domains:
- '[[domains/supply-chain]]'
tier: supporting
purpose: Calculate the total cost of serving each customer, channel, or product segment
  including fulfilment, returns, and support costs.
when_to_use: When profitability by customer or channel is unclear due to shared cost
  pooling.
diagnostic_questions:
- Which customers or channels are most expensive to serve relative to their margin
  contribution?
- Does pricing cover cost-to-serve for all customer segments?
success_metrics:
- Cost-to-serve per customer / per order
- Profitable customer %
common_risks:
- Cost-to-serve is a point-in-time snapshot — ignoring scale effects over time
common_mistakes:
- Using average cost-to-serve rather than marginal cost for pricing and customer investment
  decisions
related_frameworks:
- '[[frameworks/scor-network-optimization]]'
version: '0.1'
---

# Cost-to-Serve Analysis

**Domain(s).** [[domains/supply-chain]]

**Purpose.** Calculate the total cost of serving each customer, channel, or product segment including fulfilment, returns, and support costs.

**When to use.** When profitability by customer or channel is unclear due to shared cost pooling.

## Diagnostic questions
- Which customers or channels are most expensive to serve relative to their margin contribution?
- Does pricing cover cost-to-serve for all customer segments?

## Success metrics
- Cost-to-serve per customer / per order
- Profitable customer %

## Common risks
- Cost-to-serve is a point-in-time snapshot — ignoring scale effects over time

## Common mistakes
- Using average cost-to-serve rather than marginal cost for pricing and customer investment decisions

## Related frameworks
- [[frameworks/scor-network-optimization]]

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
