---
id: fw_launch_economics_gtm
type: framework
title: Launch Economics & GTM
tags:
- framework
- new-product-launch
source: ADR-004 §3 (Consulting Knowledge Library)
last_verified: '2026-07-06'
status: draft
visibility: global
name: Launch Economics & GTM
domains:
- '[[domains/new-product-launch]]'
tier: primary
purpose: Validate demand and willingness-to-pay before feasibility, then size unit
  economics and GTM.
when_to_use: Launch go/no-go and go-to-market planning.
diagnostic_questions:
- Is there real demand and willingness-to-pay?
- Is it net incremental after cannibalization?
success_metrics:
- Contribution margin per unit
- Breakeven volume
- Adoption ramp
common_risks:
- Straight-line adoption assumptions
common_mistakes:
- Assuming buildable means wanted
- Ignoring cannibalization
related_frameworks: []
version: '0.1'
---

# Launch Economics & GTM

**Domain.** [[domains/new-product-launch]]

**Purpose.** Validate demand and willingness-to-pay before feasibility, then size unit economics and GTM.

**When to use.** Launch go/no-go and go-to-market planning.
**When not to use.** When there is no demand signal yet.

## Logic
Demand (JTBD·WTP·size) → competition/substitutes → unit economics + cannibalization → GTM (channel·price·sequence).

## Diagnostic questions
- Is there real demand and willingness-to-pay?
- Is it net incremental after cannibalization?

## Success metrics
- Contribution margin per unit
- Breakeven volume
- Adoption ramp

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
