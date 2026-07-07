---
id: fw_contrib_margin
type: framework
title: Contribution Margin Analysis
tags:
- framework
- supporting
source: ADR-004 §3 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
name: Contribution Margin Analysis
domains:
- '[[domains/profitability]]'
tier: supporting
purpose: Compute revenue minus variable costs per product/segment to identify which
  lines drive or destroy margin.
when_to_use: When fixed-cost allocation obscures per-segment or per-product profitability.
diagnostic_questions:
- Which product lines have negative or thin contribution margin?
- Are variable costs growing faster than revenue in any segment?
success_metrics:
- Contribution margin per unit
- Contribution margin %
common_risks:
- Misclassifying semi-variable costs as purely fixed
common_mistakes:
- Using total allocated cost instead of marginal cost for the analysis
related_frameworks:
- '[[frameworks/profit-tree]]'
version: '0.1'
---

# Contribution Margin Analysis

**Domain(s).** [[domains/profitability]]

**Purpose.** Compute revenue minus variable costs per product/segment to identify which lines drive or destroy margin.

**When to use.** When fixed-cost allocation obscures per-segment or per-product profitability.

## Diagnostic questions
- Which product lines have negative or thin contribution margin?
- Are variable costs growing faster than revenue in any segment?

## Success metrics
- Contribution margin per unit
- Contribution margin %

## Common risks
- Misclassifying semi-variable costs as purely fixed

## Common mistakes
- Using total allocated cost instead of marginal cost for the analysis

## Related frameworks
- [[frameworks/profit-tree]]

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
