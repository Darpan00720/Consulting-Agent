---
id: fw_cannib_npv
type: framework
title: Cannibalization-Adjusted NPV
tags:
- framework
- supporting
source: ADR-004 §3 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
name: Cannibalization-Adjusted NPV
domains:
- '[[domains/new-product-launch]]'
tier: supporting
purpose: Compute the net present value of a new product launch adjusted for revenue
  cannibalized from existing portfolio products.
when_to_use: When a new product competes directly with existing products in the current
  portfolio.
diagnostic_questions:
- What % of new product revenue will cannibalize existing products?
- Is net incremental contribution positive after accounting for cannibalization?
success_metrics:
- Net incremental contribution margin
- Net NPV after cannibalization
common_risks:
- Systematically underestimating cannibalization rate in early-stage forecasts
common_mistakes:
- Ignoring cannibalization entirely or treating all new product revenue as purely
  incremental
related_frameworks:
- '[[frameworks/launch-economics-gtm]]'
version: '0.1'
---

# Cannibalization-Adjusted NPV

**Domain(s).** [[domains/new-product-launch]]

**Purpose.** Compute the net present value of a new product launch adjusted for revenue cannibalized from existing portfolio products.

**When to use.** When a new product competes directly with existing products in the current portfolio.

## Diagnostic questions
- What % of new product revenue will cannibalize existing products?
- Is net incremental contribution positive after accounting for cannibalization?

## Success metrics
- Net incremental contribution margin
- Net NPV after cannibalization

## Common risks
- Systematically underestimating cannibalization rate in early-stage forecasts

## Common mistakes
- Ignoring cannibalization entirely or treating all new product revenue as purely incremental

## Related frameworks
- [[frameworks/launch-economics-gtm]]

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
