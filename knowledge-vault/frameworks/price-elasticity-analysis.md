---
id: fw_price_elasticity
type: framework
title: Price Elasticity Analysis
tags:
- framework
- supporting
source: ADR-004 §3 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
name: Price Elasticity Analysis
domains:
- '[[domains/pricing]]'
tier: supporting
purpose: Measure how demand responds to price changes to inform pricing decisions.
when_to_use: When setting or adjusting prices and the volume impact of price changes
  is uncertain.
diagnostic_questions:
- How does volume change with a 1% price increase in each segment?
- Is demand elastic or inelastic in this segment and competitive context?
success_metrics:
- Price elasticity coefficient by segment
- Revenue response to a test price change
common_risks:
- Estimating elasticity from periods with confounding promotions or macro shifts
common_mistakes:
- Applying aggregate elasticity to segments with very different price sensitivities
related_frameworks:
- '[[frameworks/value-based-pricing]]'
version: '0.1'
---

# Price Elasticity Analysis

**Domain(s).** [[domains/pricing]]

**Purpose.** Measure how demand responds to price changes to inform pricing decisions.

**When to use.** When setting or adjusting prices and the volume impact of price changes is uncertain.

## Diagnostic questions
- How does volume change with a 1% price increase in each segment?
- Is demand elastic or inelastic in this segment and competitive context?

## Success metrics
- Price elasticity coefficient by segment
- Revenue response to a test price change

## Common risks
- Estimating elasticity from periods with confounding promotions or macro shifts

## Common mistakes
- Applying aggregate elasticity to segments with very different price sensitivities

## Related frameworks
- [[frameworks/value-based-pricing]]

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
