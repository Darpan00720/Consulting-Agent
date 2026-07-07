---
id: fw_retention_econ
type: framework
title: Retention Economics
tags:
- framework
- supporting
source: ADR-004 §3 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
name: Retention Economics
domains:
- '[[domains/customer-strategy]]'
tier: supporting
purpose: Model the financial impact of improving retention rates across customer segments
  to build the investment case for retention programs.
when_to_use: When churn is a key driver of value destruction and allocating investment
  between retention and acquisition.
diagnostic_questions:
- What is the revenue and margin impact of a 1-percentage-point reduction in churn?
- Which segment's retention improvement has the highest LTV impact?
success_metrics:
- Retention rate by segment
- LTV improvement per retention point
- Payback period on retention investment
common_risks:
- Retaining unprofitable customers with high lifetime service costs
common_mistakes:
- Spending retention budget broadly rather than targeting high-LTV-at-risk customers
related_frameworks:
- '[[frameworks/segmentation-clv]]'
version: '0.1'
---

# Retention Economics

**Domain(s).** [[domains/customer-strategy]]

**Purpose.** Model the financial impact of improving retention rates across customer segments to build the investment case for retention programs.

**When to use.** When churn is a key driver of value destruction and allocating investment between retention and acquisition.

## Diagnostic questions
- What is the revenue and margin impact of a 1-percentage-point reduction in churn?
- Which segment's retention improvement has the highest LTV impact?

## Success metrics
- Retention rate by segment
- LTV improvement per retention point
- Payback period on retention investment

## Common risks
- Retaining unprofitable customers with high lifetime service costs

## Common mistakes
- Spending retention budget broadly rather than targeting high-LTV-at-risk customers

## Related frameworks
- [[frameworks/segmentation-clv]]

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
