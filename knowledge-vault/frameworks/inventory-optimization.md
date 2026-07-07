---
id: fw_inventory_opt
type: framework
title: Inventory Optimization (Safety Stock / EOQ)
tags:
- framework
- supporting
source: ADR-004 §3 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
name: Inventory Optimization (Safety Stock / EOQ)
domains:
- '[[domains/supply-chain]]'
tier: supporting
purpose: Set optimal inventory levels using safety stock and economic order quantity
  to balance service levels against holding cost.
when_to_use: When inventory is too high (working capital drain) or too low (stock-outs
  damaging service levels).
diagnostic_questions:
- What demand and lead-time variability is driving safety stock requirements?
- Where in the network is excess inventory held relative to service requirements?
success_metrics:
- Inventory turns
- Days inventory outstanding (DIO)
- Stock-out rate
common_risks:
- Optimizing at the individual node level rather than the network level
common_mistakes:
- Setting safety stock without modeling lead-time variability alongside demand variability
related_frameworks:
- '[[frameworks/scor-network-optimization]]'
version: '0.1'
---

# Inventory Optimization (Safety Stock / EOQ)

**Domain(s).** [[domains/supply-chain]]

**Purpose.** Set optimal inventory levels using safety stock and economic order quantity to balance service levels against holding cost.

**When to use.** When inventory is too high (working capital drain) or too low (stock-outs damaging service levels).

## Diagnostic questions
- What demand and lead-time variability is driving safety stock requirements?
- Where in the network is excess inventory held relative to service requirements?

## Success metrics
- Inventory turns
- Days inventory outstanding (DIO)
- Stock-out rate

## Common risks
- Optimizing at the individual node level rather than the network level

## Common mistakes
- Setting safety stock without modeling lead-time variability alongside demand variability

## Related frameworks
- [[frameworks/scor-network-optimization]]

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
