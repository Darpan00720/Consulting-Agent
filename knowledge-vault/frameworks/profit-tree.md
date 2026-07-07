---
id: fw_profit_tree
type: framework
title: Profit Tree
tags:
- framework
- profitability
source: ADR-004 §3 (Consulting Knowledge Library)
last_verified: '2026-07-06'
status: draft
visibility: global
name: Profit Tree
domains:
- '[[domains/profitability]]'
tier: primary
purpose: Decompose profit into revenue (price·volume·mix) and cost drivers to isolate
  what moved.
when_to_use: Diagnosing a profit or margin decline in an established business.
diagnostic_questions:
- Is the decline sudden or gradual?
- Is it uniform or concentrated in a segment?
- Is it price, volume, or cost?
success_metrics:
- Operating margin
- Gross margin
- Contribution margin
common_risks:
- Confusing one-time effects with structural decline
common_mistakes:
- Cutting cost before confirming a cost problem
related_frameworks: []
version: '0.1'
---

# Profit Tree

**Domain.** [[domains/profitability]]

**Purpose.** Decompose profit into revenue (price·volume·mix) and cost drivers to isolate what moved.

**When to use.** Diagnosing a profit or margin decline in an established business.
**When not to use.** Greenfield situations with no existing P&L.

## Logic
Δprofit → revenue (price·volume·mix) vs cost (fixed·variable, which line); isolate the delta → segment → attack the dominant driver.

## Diagnostic questions
- Is the decline sudden or gradual?
- Is it uniform or concentrated in a segment?
- Is it price, volume, or cost?

## Success metrics
- Operating margin
- Gross margin
- Contribution margin

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
