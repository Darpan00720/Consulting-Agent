---
id: kpi_revenue
type: kpi
title: Revenue
tags:
- kpi
- revenue-growth
- profitability
source: ADR-004 §5 (Consulting Knowledge Library)
last_verified: '2026-07-08'
status: draft
visibility: global
formula: "Sigma (price x volume)"
unit: currency
---

# Revenue

**Lead/Lag.** Lagging indicator. [Verified: ADR-004 §5]

**Interpretation.** Top-line scale; the total inflow from core business operations across all
products, channels, and periods. [Verified: ADR-004 §5]

**Formula.** Sum of (price × volume) across all transactions.

**Data needs.** Transaction records with price and quantity by product, channel, and period.
[Verified: ADR-004 §5]

**Industry differences.** Revenue recognition rules differ materially: SaaS businesses
recognise revenue ratably over the contract period; retail recognises at point-of-sale.
Cross-industry comparisons require normalisation for recognition-policy differences.
[Verified: ADR-004 §5]

**Relevant domains.**
- [[domains/revenue-growth]]
- [[domains/profitability]]
- [[domains/sales-and-marketing]]
- [[domains/new-product-launch]]

**Related frameworks.**
- [[frameworks/profit-tree]] — decomposes revenue into price and volume drivers
- [[frameworks/growth-driver-tree]] — traces top-line growth to its underlying drivers
- [[frameworks/segment-pl-analysis]] — disaggregates revenue by segment or business unit
- [[frameworks/contribution-margin-analysis]] — links revenue to variable-cost contribution

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
