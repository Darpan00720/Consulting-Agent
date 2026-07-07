---
id: fw_comp_multiples
type: framework
title: Comparable Company & Transaction Multiples
tags:
- framework
- supporting
source: ADR-004 §3 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
name: Comparable Company & Transaction Multiples
domains:
- '[[domains/m-and-a]]'
tier: supporting
purpose: Value a business by applying market-derived multiples (EV/EBITDA, P/E, EV/Revenue)
  from comparable companies or transactions.
when_to_use: When market data is available and a market-referenced valuation is needed
  to triangulate the DCF.
diagnostic_questions:
- Are the selected comps truly comparable on business model, size, and risk profile?
- Are current market multiples at a cyclical peak or trough?
success_metrics:
- Implied EV range vs. DCF standalone value
- Acquisition multiple vs. comparable transaction range
common_risks:
- Market mispricing propagated directly into the target valuation
common_mistakes:
- Using revenue multiples to compare companies with very different margin profiles
related_frameworks:
- '[[frameworks/synergy-valuation]]'
version: '0.1'
---

# Comparable Company & Transaction Multiples

**Domain(s).** [[domains/m-and-a]]

**Purpose.** Value a business by applying market-derived multiples (EV/EBITDA, P/E, EV/Revenue) from comparable companies or transactions.

**When to use.** When market data is available and a market-referenced valuation is needed to triangulate the DCF.

## Diagnostic questions
- Are the selected comps truly comparable on business model, size, and risk profile?
- Are current market multiples at a cyclical peak or trough?

## Success metrics
- Implied EV range vs. DCF standalone value
- Acquisition multiple vs. comparable transaction range

## Common risks
- Market mispricing propagated directly into the target valuation

## Common mistakes
- Using revenue multiples to compare companies with very different margin profiles

## Related frameworks
- [[frameworks/synergy-valuation]]

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
