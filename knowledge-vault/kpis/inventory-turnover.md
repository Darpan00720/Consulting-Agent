---
id: kpi_inventory_turnover
type: kpi
title: Inventory Turnover
aliases:
- Inventory Turns
tags:
- kpi
- supply-chain
source: ADR-004 §5 (Consulting Knowledge Library)
last_verified: '2026-07-08'
status: draft
visibility: global
formula: "COGS / Average Inventory"
unit: "turns per period"
---

# Inventory Turnover

**Lead/Lag.** Lagging indicator; reflects recent inventory management efficiency.
[Verified: ADR-004 §5]

**Interpretation.** How many times inventory is sold and replenished in a period; higher
turns indicate leaner operations with less capital tied up in stock and lower obsolescence
risk. [Verified: ADR-004 §5]

**Formula.** Cost of Goods Sold / Average Inventory balance for the period.

**Data needs.** COGS from the income statement and beginning/ending inventory balances from
the balance sheet to compute the average. [Verified: ADR-004 §5]

**Industry differences.** Not meaningful for pure service businesses with no physical
inventory. Retail targets high turns especially in fast-moving consumer goods; manufacturing
turns depend on production cycle length and supply lead times. [Verified: ADR-004 §5]

**Relevant domains.**
- [[domains/supply-chain]]

**Related frameworks.**
- [[frameworks/inventory-optimization]] — optimises reorder points and safety stock to improve turns
- [[frameworks/scor-network-optimization]] — analyses network design to reduce inventory holding

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
