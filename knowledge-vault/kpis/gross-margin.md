---
id: kpi_gross_margin
type: kpi
title: Gross Margin
tags:
- kpi
- profitability
- pricing
- cost-reduction
source: ADR-004 §5 (Consulting Knowledge Library)
last_verified: '2026-07-08'
status: draft
visibility: global
formula: "(Revenue - COGS) / Revenue"
unit: "%"
---

# Gross Margin

**Lead/Lag.** Lagging indicator. [Verified: ADR-004 §5]

**Interpretation.** Combined signal of pricing power and production or sourcing efficiency;
the residual margin after removing direct costs from revenue. [Verified: ADR-004 §5]

**Formula.** (Revenue − Cost of Goods Sold) / Revenue × 100.

**Data needs.** Revenue and COGS from the income statement, segmented by product line
where possible. [Verified: ADR-004 §5]

**Industry differences.** COGS scope varies by sector: manufacturing includes raw materials
and direct labour; retail includes purchase cost and inbound freight; services may include
only direct delivery costs. These definitional differences make cross-sector comparisons
unreliable without normalisation. [Verified: ADR-004 §5]

**Relevant domains.**
- [[domains/profitability]]
- [[domains/pricing]]
- [[domains/cost-reduction]]

**Related frameworks.**
- [[frameworks/profit-tree]] — positions gross margin in the profit decomposition
- [[frameworks/contribution-margin-analysis]] — extends to variable vs fixed cost structure
- [[frameworks/cost-decomposition-benchmarking]] — benchmarks COGS components against peers

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
