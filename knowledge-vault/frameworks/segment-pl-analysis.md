---
id: fw_seg_pl
type: framework
title: Segment P&L Analysis
tags:
- framework
- supporting
source: ADR-004 §3 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
name: Segment P&L Analysis
domains:
- '[[domains/profitability]]'
tier: supporting
purpose: Reconstruct profit-and-loss statements by customer, product, or geography
  segment to surface where profit is concentrated or lost.
when_to_use: When aggregate P&L masks material performance differences across segments.
diagnostic_questions:
- Which segments are profitable and which are loss-making?
- Is the mix of segments shifting toward lower-margin ones?
success_metrics:
- Segment operating margin
- Segment revenue share
common_risks:
- Arbitrary overhead allocation distorting segment profitability
common_mistakes:
- Stopping at segment revenue without tracing costs to each segment
related_frameworks:
- '[[frameworks/profit-tree]]'
version: '0.1'
---

# Segment P&L Analysis

**Domain(s).** [[domains/profitability]]

**Purpose.** Reconstruct profit-and-loss statements by customer, product, or geography segment to surface where profit is concentrated or lost.

**When to use.** When aggregate P&L masks material performance differences across segments.

## Diagnostic questions
- Which segments are profitable and which are loss-making?
- Is the mix of segments shifting toward lower-margin ones?

## Success metrics
- Segment operating margin
- Segment revenue share

## Common risks
- Arbitrary overhead allocation distorting segment profitability

## Common mistakes
- Stopping at segment revenue without tracing costs to each segment

## Related frameworks
- [[frameworks/profit-tree]]

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
