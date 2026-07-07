---
id: fw_dcf
type: framework
title: Discounted Cash Flow (DCF) Valuation
tags:
- framework
- supporting
source: ADR-004 §3 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
name: Discounted Cash Flow (DCF) Valuation
domains:
- '[[domains/m-and-a]]'
tier: supporting
purpose: Value a business or asset by discounting projected free cash flows at the
  appropriate risk-adjusted discount rate (WACC).
when_to_use: When valuing acquisition targets, evaluating strategic investments, or
  testing deal economics.
diagnostic_questions:
- What are the key FCF drivers and their sensitivities to base-case assumptions?
- How sensitive is the implied value to WACC and terminal growth rate assumptions?
success_metrics:
- DCF equity value range
- IRR vs. WACC spread
common_risks:
- Garbage-in garbage-out from management's optimistic long-range projections
common_mistakes:
- Not stress-testing terminal value, which typically drives 60–80% of DCF equity value
related_frameworks:
- '[[frameworks/synergy-valuation]]'
version: '0.1'
---

# Discounted Cash Flow (DCF) Valuation

**Domain(s).** [[domains/m-and-a]]

**Purpose.** Value a business or asset by discounting projected free cash flows at the appropriate risk-adjusted discount rate (WACC).

**When to use.** When valuing acquisition targets, evaluating strategic investments, or testing deal economics.

## Diagnostic questions
- What are the key FCF drivers and their sensitivities to base-case assumptions?
- How sensitive is the implied value to WACC and terminal growth rate assumptions?

## Success metrics
- DCF equity value range
- IRR vs. WACC spread

## Common risks
- Garbage-in garbage-out from management's optimistic long-range projections

## Common mistakes
- Not stress-testing terminal value, which typically drives 60–80% of DCF equity value

## Related frameworks
- [[frameworks/synergy-valuation]]

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
