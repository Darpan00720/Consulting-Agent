---
id: fw_cost_decomposition_benchmarking
type: framework
title: Cost Decomposition & Benchmarking
tags:
- framework
- cost-reduction
source: ADR-004 §3 (Consulting Knowledge Library)
last_verified: '2026-07-06'
status: draft
visibility: global
name: Cost Decomposition & Benchmarking
domains:
- '[[domains/cost-reduction]]'
tier: primary
purpose: Decompose the cost base, benchmark it, and prioritize levers by savings ×
  feasibility × risk.
when_to_use: When cost is confirmed as the driver of a margin problem.
diagnostic_questions:
- Which cost buckets are out of line versus benchmark?
- Are they controllable?
success_metrics:
- Cost-to-serve
- SG&A %
- Run-rate savings
common_risks:
- Cutting capability needed for growth
common_mistakes:
- Across-the-board cuts
- Booking savings without implementation cost
related_frameworks: []
version: '0.1'
---

# Cost Decomposition & Benchmarking

**Domain.** [[domains/cost-reduction]]

**Purpose.** Decompose the cost base, benchmark it, and prioritize levers by savings × feasibility × risk.

**When to use.** When cost is confirmed as the driver of a margin problem.
**When not to use.** Revenue-driven margin problems.

## Logic
Fixed/variable, direct/overhead, controllable/structural; decompose → benchmark → prioritize.

## Diagnostic questions
- Which cost buckets are out of line versus benchmark?
- Are they controllable?

## Success metrics
- Cost-to-serve
- SG&A %
- Run-rate savings

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
