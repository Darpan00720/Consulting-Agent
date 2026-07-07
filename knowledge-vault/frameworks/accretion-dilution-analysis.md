---
id: fw_accretion_dilution
type: framework
title: Accretion / Dilution Analysis
tags:
- framework
- supporting
source: ADR-004 §3 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
name: Accretion / Dilution Analysis
domains:
- '[[domains/m-and-a]]'
tier: supporting
purpose: Assess whether a transaction increases (accretes) or decreases (dilutes)
  acquirer EPS or other per-share metrics.
when_to_use: For public company acquirers where EPS impact is a key board and market
  concern.
diagnostic_questions:
- Does the deal accrete or dilute EPS in Year 1 and Year 3 under base-case assumptions?
- At what premium does the EPS impact break even?
success_metrics:
- Year-1 EPS accretion/dilution %
- Breakeven premium vs. offer price
common_risks:
- EPS accretion masking long-run ROIC destruction when debt financing is cheap
common_mistakes:
- Optimizing for short-run EPS accretion at the expense of long-term return on invested
  capital
related_frameworks:
- '[[frameworks/synergy-valuation]]'
version: '0.1'
---

# Accretion / Dilution Analysis

**Domain(s).** [[domains/m-and-a]]

**Purpose.** Assess whether a transaction increases (accretes) or decreases (dilutes) acquirer EPS or other per-share metrics.

**When to use.** For public company acquirers where EPS impact is a key board and market concern.

## Diagnostic questions
- Does the deal accrete or dilute EPS in Year 1 and Year 3 under base-case assumptions?
- At what premium does the EPS impact break even?

## Success metrics
- Year-1 EPS accretion/dilution %
- Breakeven premium vs. offer price

## Common risks
- EPS accretion masking long-run ROIC destruction when debt financing is cheap

## Common mistakes
- Optimizing for short-run EPS accretion at the expense of long-term return on invested capital

## Related frameworks
- [[frameworks/synergy-valuation]]

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
