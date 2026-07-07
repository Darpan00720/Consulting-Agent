---
id: fw_build_buy_partner
type: framework
title: Build / Buy / Partner Decision
tags:
- framework
- supporting
source: ADR-004 §3 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
name: Build / Buy / Partner Decision
domains:
- '[[domains/ai-strategy]]'
tier: supporting
purpose: Evaluate whether to build AI capabilities internally, buy a vendor solution,
  or partner with a specialist provider.
when_to_use: When deciding how to source AI capabilities for a prioritized use case.
diagnostic_questions:
- Is competitive differentiation dependent on proprietary AI capability?
- Does a vendor solution already solve 80% of the need with acceptable limitations?
success_metrics:
- Time-to-value by sourcing option (months)
- Capability ownership score vs. strategic importance
common_risks:
- Defaulting to build for capabilities where vendor solutions are faster and cheaper
common_mistakes:
- Not modeling the total cost of ownership for build (data, talent, maintenance) vs.
  buy
related_frameworks:
- '[[frameworks/ai-use-case-portfolio]]'
version: '0.1'
---

# Build / Buy / Partner Decision

**Domain(s).** [[domains/ai-strategy]]

**Purpose.** Evaluate whether to build AI capabilities internally, buy a vendor solution, or partner with a specialist provider.

**When to use.** When deciding how to source AI capabilities for a prioritized use case.

## Diagnostic questions
- Is competitive differentiation dependent on proprietary AI capability?
- Does a vendor solution already solve 80% of the need with acceptable limitations?

## Success metrics
- Time-to-value by sourcing option (months)
- Capability ownership score vs. strategic importance

## Common risks
- Defaulting to build for capabilities where vendor solutions are faster and cheaper

## Common mistakes
- Not modeling the total cost of ownership for build (data, talent, maintenance) vs. buy

## Related frameworks
- [[frameworks/ai-use-case-portfolio]]

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
