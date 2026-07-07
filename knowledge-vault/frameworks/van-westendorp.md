---
id: fw_van_westendorp
type: framework
title: Van Westendorp Price Sensitivity Meter
tags:
- framework
- supporting
source: ADR-004 §3 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
name: Van Westendorp Price Sensitivity Meter
domains:
- '[[domains/pricing]]'
tier: supporting
purpose: Identify an acceptable price range and optimal price point via four-question
  survey (too cheap / cheap / expensive / too expensive).
when_to_use: When direct WTP measurement is needed quickly, without a full conjoint
  design.
diagnostic_questions:
- At what price does the product feel too cheap to be credible?
- At what price does the product become too expensive to consider?
success_metrics:
- Acceptable price range (PMC to PME)
- Optimal price point (intersection of acceptable and expensive curves)
common_risks:
- Anchoring bias from prior price exposure affecting survey responses
common_mistakes:
- Using Van Westendorp alone without testing competitive context and switching thresholds
related_frameworks:
- '[[frameworks/value-based-pricing]]'
version: '0.1'
---

# Van Westendorp Price Sensitivity Meter

**Domain(s).** [[domains/pricing]]

**Purpose.** Identify an acceptable price range and optimal price point via four-question survey (too cheap / cheap / expensive / too expensive).

**When to use.** When direct WTP measurement is needed quickly, without a full conjoint design.

## Diagnostic questions
- At what price does the product feel too cheap to be credible?
- At what price does the product become too expensive to consider?

## Success metrics
- Acceptable price range (PMC to PME)
- Optimal price point (intersection of acceptable and expensive curves)

## Common risks
- Anchoring bias from prior price exposure affecting survey responses

## Common mistakes
- Using Van Westendorp alone without testing competitive context and switching thresholds

## Related frameworks
- [[frameworks/value-based-pricing]]

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
