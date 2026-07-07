---
id: fw_channel_mix
type: framework
title: Channel Mix Optimization
tags:
- framework
- supporting
source: ADR-004 §3 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
name: Channel Mix Optimization
domains:
- '[[domains/sales-and-marketing]]'
tier: supporting
purpose: Evaluate the cost and revenue contribution of each sales and marketing channel
  to optimize the go-to-market channel mix.
when_to_use: When CAC differs materially across channels and budget allocation appears
  suboptimal.
diagnostic_questions:
- Which channels deliver the lowest CAC and acquire the highest-LTV customers?
- Are we over-invested in high-CAC channels relative to their LTV contribution?
success_metrics:
- CAC by channel
- LTV:CAC ratio by channel
- Revenue contribution by channel
common_risks:
- Attribution errors from multi-touch customer journeys distorting channel ROI
common_mistakes:
- Optimizing for first-touch or last-touch attribution while ignoring the full customer
  journey
related_frameworks:
- '[[frameworks/funnel-gtm-economics]]'
version: '0.1'
---

# Channel Mix Optimization

**Domain(s).** [[domains/sales-and-marketing]]

**Purpose.** Evaluate the cost and revenue contribution of each sales and marketing channel to optimize the go-to-market channel mix.

**When to use.** When CAC differs materially across channels and budget allocation appears suboptimal.

## Diagnostic questions
- Which channels deliver the lowest CAC and acquire the highest-LTV customers?
- Are we over-invested in high-CAC channels relative to their LTV contribution?

## Success metrics
- CAC by channel
- LTV:CAC ratio by channel
- Revenue contribution by channel

## Common risks
- Attribution errors from multi-touch customer journeys distorting channel ROI

## Common mistakes
- Optimizing for first-touch or last-touch attribution while ignoring the full customer journey

## Related frameworks
- [[frameworks/funnel-gtm-economics]]

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
