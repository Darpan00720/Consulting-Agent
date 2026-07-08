---
id: kpi_cac
type: kpi
title: Customer Acquisition Cost
aliases:
- CAC
tags:
- kpi
- sales-and-marketing
- revenue-growth
- customer-strategy
source: ADR-004 §5 (Consulting Knowledge Library)
last_verified: '2026-07-08'
status: draft
visibility: global
formula: "Sales & Marketing spend / New customers acquired"
unit: "currency / new customer"
---

# Customer Acquisition Cost (CAC)

**Lead/Lag.** Leading indicator; a rising CAC trend predicts future margin compression
before it appears in P&L results. [Verified: ADR-004 §5]

**Interpretation.** Average cost to acquire one net-new customer through sales and marketing
activity. Must be assessed relative to [[kpis/ltv|LTV]] to determine whether acquisition
investment is economically justified. [Verified: ADR-004 §5]

**Formula.** Total Sales & Marketing Spend in the period / Net new customers acquired
in the period.

**Data needs.** Fully loaded (or consistently defined partial) marketing and sales spend,
and net new customer count with clear definition of "new." [Verified: ADR-004 §5]

**Industry differences.** B2B CAC is materially higher than B2C due to longer enterprise
sales cycles, complex multi-stakeholder evaluations, and higher sales-force cost per deal.
[Verified: ADR-004 §5]

**Relevant domains.**
- [[domains/sales-and-marketing]]
- [[domains/revenue-growth]]
- [[domains/customer-strategy]]

**Related frameworks.**
- [[frameworks/cac-ltv-analysis]] — pairs CAC with LTV to compute unit economics
- [[frameworks/funnel-gtm-economics]] — traces spend through the acquisition funnel to CAC
- [[frameworks/channel-mix-optimization]] — disaggregates CAC by acquisition channel

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
