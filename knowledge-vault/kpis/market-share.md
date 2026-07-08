---
id: kpi_market_share
type: kpi
title: Market Share
tags:
- kpi
- market-entry
- revenue-growth
- corporate-strategy
source: ADR-004 §5 (Consulting Knowledge Library)
last_verified: '2026-07-08'
status: draft
visibility: global
formula: "Company revenue / Total market revenue"
unit: "%"
---

# Market Share

**Lead/Lag.** Lagging indicator; reflects the accumulated effect of competitive actions
taken in prior periods. [Verified: ADR-004 §5]

**Interpretation.** Relative competitive position within a defined market boundary. Higher
share typically correlates with pricing power, scale economies, and distribution leverage.
[Verified: ADR-004 §5]

**Formula.** Company Revenue / Total Market Revenue × 100.

**Data needs.** Company revenue (available internally) plus total market revenue (requires
external market sizing data from industry reports or primary research). [Verified: ADR-004 §5]

**Industry differences.** Market definition sensitivity is high: narrowing or broadening
the market boundary materially changes the measured share figure. Results are meaningful
only when the market boundary is held constant across comparison periods. [Verified: ADR-004 §5]

**Relevant domains.**
- [[domains/market-entry]]
- [[domains/revenue-growth]]
- [[domains/corporate-strategy]]

**Related frameworks.**
- [[frameworks/market-competitive-analysis]] — maps competitive position and share dynamics
- [[frameworks/tam-sam-som]] — provides the market denominator for share calculation
- [[frameworks/bcg-growth-share-matrix]] — uses relative market share as a portfolio positioning axis

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
