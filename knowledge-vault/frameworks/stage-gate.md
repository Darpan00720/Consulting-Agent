---
id: fw_stage_gate
type: framework
title: Stage-Gate Product Development
tags:
- framework
- supporting
source: ADR-004 §3 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
name: Stage-Gate Product Development
domains:
- '[[domains/new-product-launch]]'
tier: supporting
purpose: Control product development investment through sequential decision gates,
  each requiring evidence before proceeding to the next stage.
when_to_use: When managing investment in uncertain new product development where early
  kills save capital.
diagnostic_questions:
- Does current evidence justify investment to proceed to the next stage?
- What evidence would falsify the hypothesis at this gate?
success_metrics:
- Kill rate at early gates (higher = more capital-efficient)
- Cycle time per stage
common_risks:
- Political pressure preventing early kills on struggling projects
common_mistakes:
- Treating gates as progress milestones rather than genuine go/no-go decision points
related_frameworks:
- '[[frameworks/launch-economics-gtm]]'
version: '0.1'
---

# Stage-Gate Product Development

**Domain(s).** [[domains/new-product-launch]]

**Purpose.** Control product development investment through sequential decision gates, each requiring evidence before proceeding to the next stage.

**When to use.** When managing investment in uncertain new product development where early kills save capital.

## Diagnostic questions
- Does current evidence justify investment to proceed to the next stage?
- What evidence would falsify the hypothesis at this gate?

## Success metrics
- Kill rate at early gates (higher = more capital-efficient)
- Cycle time per stage

## Common risks
- Political pressure preventing early kills on struggling projects

## Common mistakes
- Treating gates as progress milestones rather than genuine go/no-go decision points

## Related frameworks
- [[frameworks/launch-economics-gtm]]

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
