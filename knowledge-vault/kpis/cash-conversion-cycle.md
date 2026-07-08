---
id: kpi_cash_conversion_cycle
type: kpi
title: Cash Conversion Cycle
aliases:
- CCC
tags:
- kpi
- supply-chain
- m-and-a
source: ADR-004 §5 (Consulting Knowledge Library)
last_verified: '2026-07-08'
status: draft
visibility: global
formula: "DSO + DIO - DPO"
unit: days
---

# Cash Conversion Cycle (CCC)

**Lead/Lag.** Lagging indicator; reflects recent working capital efficiency.
[Verified: ADR-004 §5]

**Interpretation.** Number of days between spending cash on inputs and receiving cash from
customers. A shorter (or negative) cycle means the business self-funds operations; a longer
cycle requires working capital financing. [Verified: ADR-004 §5]

**Formula.** Days Sales Outstanding (DSO) + Days Inventory Outstanding (DIO) −
Days Payable Outstanding (DPO).

**Data needs.** Accounts receivable, inventory, and accounts payable balances; revenue and
COGS for the per-day denominators. [Verified: ADR-004 §5]

**Industry differences.** Retail often achieves short or negative cycles by collecting
cash before paying suppliers; manufacturing cycles are long due to raw-material lead times
and production schedules. [Verified: ADR-004 §5]

**Relevant domains.**
- [[domains/supply-chain]]
- [[domains/m-and-a]]

**Related frameworks.**
- [[frameworks/scor-network-optimization]] — maps supply chain flows that drive DSO, DIO, and DPO
- [[frameworks/inventory-optimization]] — targets DIO reduction through leaner inventory policies

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
