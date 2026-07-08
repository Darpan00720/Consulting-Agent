---
id: kpi_ebitda
type: kpi
title: EBITDA
aliases:
- EBITDA
tags:
- kpi
- profitability
- m-and-a
- private-equity-due-diligence
source: ADR-004 §5 (Consulting Knowledge Library)
last_verified: '2026-07-08'
status: draft
visibility: global
formula: "Operating income + Depreciation + Amortisation"
unit: currency
---

# EBITDA

**Lead/Lag.** Lagging indicator. [Verified: ADR-004 §5]

**Interpretation.** Proxy for operating cash generation before the effects of capital
structure, tax policy, and accounting depreciation conventions. Widely used in M&A and
private-equity valuation as a normalised earnings base. [Verified: ADR-004 §5]

**Formula.** Earnings Before Interest, Taxes, Depreciation and Amortisation =
Operating Income + D&A add-back.

**Data needs.** P&L (operating income line) and depreciation/amortisation schedule or
notes to the financial statements. [Verified: ADR-004 §5]

**Industry differences.** High capital intensity (energy, manufacturing, telecoms) produces
large D&A charges that inflate EBITDA relative to true free cash flow; asset-light
businesses (software, consulting) show EBITDA close to EBIT. Raw EBITDA multiples are
non-comparable across capital-intensity tiers without adjustment. [Verified: ADR-004 §5]

**Relevant domains.**
- [[domains/profitability]]
- [[domains/m-and-a]]
- [[domains/private-equity-due-diligence]]

**Related frameworks.**
- [[frameworks/profit-tree]] — positions EBITDA in the earnings decomposition
- [[frameworks/discounted-cash-flow]] — uses EBITDA as a cash-flow proxy in valuation
- [[frameworks/quality-of-earnings]] — adjusts reported EBITDA for non-recurring items
- [[frameworks/comparable-multiples]] — EV/EBITDA is the most common transaction multiple

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
