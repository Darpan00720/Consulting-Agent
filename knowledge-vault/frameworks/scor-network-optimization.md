---
id: fw_scor_network_optimization
type: framework
title: SCOR & Network Optimization
tags:
- framework
- supply-chain
source: ADR-004 §3 (Consulting Knowledge Library)
last_verified: '2026-07-06'
status: draft
visibility: global
name: SCOR & Network Optimization
domains:
- '[[domains/supply-chain]]'
tier: primary
purpose: Optimize total cost-to-serve at a target service level across plan-source-make-deliver-return.
when_to_use: Network, inventory, and S&OP decisions.
diagnostic_questions:
- Where is cost-to-serve highest?
- Are there single points of failure?
success_metrics:
- Inventory turnover
- OTIF
- Cash conversion cycle
common_risks:
- Optimizing cost while breaking service or resilience
common_mistakes:
- Ignoring demand variability
related_frameworks: []
version: '0.1'
---

# SCOR & Network Optimization

**Domain.** [[domains/supply-chain]]

**Purpose.** Optimize total cost-to-serve at a target service level across plan-source-make-deliver-return.

**When to use.** Network, inventory, and S&OP decisions.
**When not to use.** Pure demand-side problems.

## Logic
Plan-source-make-deliver-return → cost vs service vs resilience trade-offs.

## Diagnostic questions
- Where is cost-to-serve highest?
- Are there single points of failure?

## Success metrics
- Inventory turnover
- OTIF
- Cash conversion cycle

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
