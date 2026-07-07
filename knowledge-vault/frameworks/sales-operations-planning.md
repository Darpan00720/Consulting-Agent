---
id: fw_sop
type: framework
title: Sales & Operations Planning (S&OP)
tags:
- framework
- supporting
source: ADR-004 §3 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
name: Sales & Operations Planning (S&OP)
domains:
- '[[domains/supply-chain]]'
tier: supporting
purpose: Align demand signals, supply capacity, and inventory plans through a regular
  cross-functional process.
when_to_use: When demand/supply mismatches create either excess inventory or recurring
  stock-outs.
diagnostic_questions:
- Is there a single demand plan that supply and commercial teams operate from?
- How quickly does the operational plan respond to demand signal changes?
success_metrics:
- Forecast accuracy (MAPE)
- OTIF (on-time in-full)
- Inventory turns
common_risks:
- S&OP becoming a reporting exercise rather than a real decision-making forum
common_mistakes:
- 'Running inconsistent demand inputs: sales forecast vs. financial plan vs. operational
  plan'
related_frameworks:
- '[[frameworks/scor-network-optimization]]'
version: '0.1'
---

# Sales & Operations Planning (S&OP)

**Domain(s).** [[domains/supply-chain]]

**Purpose.** Align demand signals, supply capacity, and inventory plans through a regular cross-functional process.

**When to use.** When demand/supply mismatches create either excess inventory or recurring stock-outs.

## Diagnostic questions
- Is there a single demand plan that supply and commercial teams operate from?
- How quickly does the operational plan respond to demand signal changes?

## Success metrics
- Forecast accuracy (MAPE)
- OTIF (on-time in-full)
- Inventory turns

## Common risks
- S&OP becoming a reporting exercise rather than a real decision-making forum

## Common mistakes
- Running inconsistent demand inputs: sales forecast vs. financial plan vs. operational plan

## Related frameworks
- [[frameworks/scor-network-optimization]]

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
