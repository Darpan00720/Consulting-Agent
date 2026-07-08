---
id: kpi_working_capital
type: kpi
title: Working Capital
aliases:
- Net Working Capital
- NWC
tags:
- kpi
- supply-chain
- m-and-a
source: ADR-004 §5 (Consulting Knowledge Library)
last_verified: '2026-07-08'
status: draft
visibility: global
formula: "Current Assets - Current Liabilities"
unit: currency
---

# Working Capital

**Lead/Lag.** Lagging indicator; reflects the balance sheet position at a point in time.
[Verified: ADR-004 §5]

**Interpretation.** Short-term liquidity buffer and measure of operating funding requirements.
Adequate working capital ensures the business can meet near-term obligations; excess working
capital may indicate collection or inventory inefficiency. [Verified: ADR-004 §5]

**Formula.** Current Assets − Current Liabilities (balance sheet items due within one year).

**Data needs.** Balance sheet with current assets and current liabilities categorised by
maturity, typically from quarterly or annual financial statements. [Verified: ADR-004 §5]

**Industry differences.** Seasonality affects working capital materially in retail (holiday
inventory build) and consumer goods. Manufacturing carries higher inventory-driven working
capital than service businesses. [Verified: ADR-004 §5]

**Relevant domains.**
- [[domains/supply-chain]]
- [[domains/m-and-a]]

**Related frameworks.**
- [[frameworks/quality-of-earnings]] — normalises working capital for one-off items in due diligence
- [[frameworks/scor-network-optimization]] — identifies supply chain levers to reduce net working capital

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
