---
id: fw_cac_ltv
type: framework
title: CAC / LTV Analysis
tags:
- framework
- supporting
source: ADR-004 §3 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
name: CAC / LTV Analysis
domains:
- '[[domains/sales-and-marketing]]'
tier: supporting
purpose: Calculate Customer Acquisition Cost and Customer Lifetime Value by segment
  and channel to assess unit economics health.
when_to_use: When evaluating growth investment levels, pricing decisions, or acquisition
  strategy.
diagnostic_questions:
- What is the LTV:CAC ratio by customer segment and acquisition channel?
- Is CAC trending up due to market saturation or execution-level inefficiency?
success_metrics:
- LTV:CAC ratio (>=3 considered healthy)
- CAC payback period (months)
common_risks:
- Using blended CAC that masks channel-mix shifts distorting the real trend
common_mistakes:
- Calculating LTV at a single assumed churn rate without sensitivity analysis
related_frameworks:
- '[[frameworks/funnel-gtm-economics]]'
version: '0.1'
---

# CAC / LTV Analysis

**Domain(s).** [[domains/sales-and-marketing]]

**Purpose.** Calculate Customer Acquisition Cost and Customer Lifetime Value by segment and channel to assess unit economics health.

**When to use.** When evaluating growth investment levels, pricing decisions, or acquisition strategy.

## Diagnostic questions
- What is the LTV:CAC ratio by customer segment and acquisition channel?
- Is CAC trending up due to market saturation or execution-level inefficiency?

## Success metrics
- LTV:CAC ratio (>=3 considered healthy)
- CAC payback period (months)

## Common risks
- Using blended CAC that masks channel-mix shifts distorting the real trend

## Common mistakes
- Calculating LTV at a single assumed churn rate without sensitivity analysis

## Related frameworks
- [[frameworks/funnel-gtm-economics]]

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
