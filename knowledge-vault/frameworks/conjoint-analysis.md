---
id: fw_conjoint
type: framework
title: Conjoint Analysis
tags:
- framework
- supporting
source: ADR-004 §3 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
name: Conjoint Analysis
domains:
- '[[domains/pricing]]'
tier: supporting
purpose: Quantify customer preferences and willingness-to-pay for product features
  via trade-off experiments.
when_to_use: When launching new products or restructuring pricing and direct WTP data
  is unavailable.
diagnostic_questions:
- Which features drive willingness-to-pay most strongly?
- What is the implied WTP for each feature bundle?
success_metrics:
- WTP range by feature configuration
- Price sensitivity coefficient by segment
common_risks:
- Hypothetical bias — stated preferences diverge from revealed purchasing behavior
common_mistakes:
- Designing surveys with too many attributes, creating respondent fatigue and noise
related_frameworks:
- '[[frameworks/value-based-pricing]]'
version: '0.1'
---

# Conjoint Analysis

**Domain(s).** [[domains/pricing]]

**Purpose.** Quantify customer preferences and willingness-to-pay for product features via trade-off experiments.

**When to use.** When launching new products or restructuring pricing and direct WTP data is unavailable.

## Diagnostic questions
- Which features drive willingness-to-pay most strongly?
- What is the implied WTP for each feature bundle?

## Success metrics
- WTP range by feature configuration
- Price sensitivity coefficient by segment

## Common risks
- Hypothetical bias — stated preferences diverge from revealed purchasing behavior

## Common mistakes
- Designing surveys with too many attributes, creating respondent fatigue and noise

## Related frameworks
- [[frameworks/value-based-pricing]]

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
