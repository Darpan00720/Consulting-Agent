---
id: kpi_roic
type: kpi
title: Return on Invested Capital
aliases:
- ROIC
tags:
- kpi
- corporate-strategy
- m-and-a
- private-equity-due-diligence
source: ADR-004 §5 (Consulting Knowledge Library)
last_verified: '2026-07-08'
status: draft
visibility: global
formula: "NOPAT / Invested Capital"
unit: "%"
---

# Return on Invested Capital (ROIC)

**Lead/Lag.** Lagging indicator; reflects the cumulative return generated on capital deployed
to date. [Verified: ADR-004 §5]

**Interpretation.** Value creation signal: ROIC above the Weighted Average Cost of Capital
(WACC) indicates economic profit; below WACC destroys shareholder value. Central to capital
allocation and M&A decisions to assess whether investments earn their hurdle rate.
[Verified: ADR-004 §5]

**Formula.** Net Operating Profit After Tax (NOPAT) / Invested Capital.

**Data needs.** NOPAT (operating income × [1 − effective tax rate]) and invested capital
(debt + equity − non-operating assets; or net PP&E + net working capital).
[Verified: ADR-004 §5]

**Industry differences.** Asset-light businesses (software, professional services) achieve
significantly higher ROIC than capital-intensive businesses (manufacturing, utilities,
telecoms). Comparing ROIC across capital-intensity tiers without adjustment is misleading.
[Verified: ADR-004 §5]

**Relevant domains.**
- [[domains/corporate-strategy]]
- [[domains/m-and-a]]
- [[domains/private-equity-due-diligence]]

**Related frameworks.**
- [[frameworks/capital-allocation-framework]] — uses ROIC vs WACC spread to prioritise reinvestment
- [[frameworks/discounted-cash-flow]] — ROIC feeds into terminal value and value-driver assumptions
- [[frameworks/comparable-multiples]] — ROIC explains premium or discount in peer comparisons

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
