---
id: fw_price_seg
type: framework
title: Price Segmentation
tags:
- framework
- supporting
source: ADR-004 §3 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
name: Price Segmentation
domains:
- '[[domains/pricing]]'
tier: supporting
purpose: Identify customer segments with different willingness-to-pay and design price
  structures to capture that variation.
when_to_use: When a single price leaves significant money on the table across segments
  with heterogeneous WTP.
diagnostic_questions:
- Are there identifiable segments with materially different willingness-to-pay?
- Can price fences between segments be maintained to prevent arbitrage?
success_metrics:
- Revenue uplift from segmented pricing vs. single price
- Pocket price realization by segment
common_risks:
- Arbitrage between price tiers undermining the segmentation structure
common_mistakes:
- Setting segment prices without modeling cross-segment migration
related_frameworks:
- '[[frameworks/value-based-pricing]]'
version: '0.1'
---

# Price Segmentation

**Domain(s).** [[domains/pricing]]

**Purpose.** Identify customer segments with different willingness-to-pay and design price structures to capture that variation.

**When to use.** When a single price leaves significant money on the table across segments with heterogeneous WTP.

## Diagnostic questions
- Are there identifiable segments with materially different willingness-to-pay?
- Can price fences between segments be maintained to prevent arbitrage?

## Success metrics
- Revenue uplift from segmented pricing vs. single price
- Pocket price realization by segment

## Common risks
- Arbitrage between price tiers undermining the segmentation structure

## Common mistakes
- Setting segment prices without modeling cross-segment migration

## Related frameworks
- [[frameworks/value-based-pricing]]

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
