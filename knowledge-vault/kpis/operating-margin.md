---
id: kpi_operating_margin
type: kpi
title: Operating Margin
tags:
- kpi
- profitability
source: ADR-004 §5 (Consulting Knowledge Library)
last_verified: '2026-07-08'
status: draft
visibility: global
formula: "Operating income / Revenue"
unit: "%"
---

# Operating Margin

**Lead/Lag.** Lagging indicator. [Verified: ADR-004 §5]

**Interpretation.** Core operating efficiency: how much operating profit is generated per
unit of revenue, capturing both COGS and operating expenses but before interest and tax.
[Verified: ADR-004 §5]

**Formula.** Operating Income / Revenue × 100.

**Data needs.** P&L with operating income and revenue clearly separated from below-the-line
items (interest, tax, one-offs). [Verified: ADR-004 §5]

**Industry differences.** Overhead allocation conventions differ across sectors: businesses
that capitalise R&D vs those that expense it show structurally different margins. High-
fixed-cost industries exhibit strong margin leverage on incremental volume. [Verified: ADR-004 §5]

**Relevant domains.**
- [[domains/profitability]]

**Related frameworks.**
- [[frameworks/profit-tree]] — decomposes operating margin into revenue and cost drivers
- [[frameworks/contribution-margin-analysis]] — separates fixed from variable cost to explain margin
- [[frameworks/segment-pl-analysis]] — identifies which segments drive or dilute overall margin

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
