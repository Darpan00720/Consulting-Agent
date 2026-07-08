---
id: kpi_ltv_cac
type: kpi
title: "LTV:CAC Ratio"
aliases:
- 'LTV:CAC'
tags:
- kpi
- sales-and-marketing
- revenue-growth
source: ADR-004 §5 (Consulting Knowledge Library)
last_verified: '2026-07-08'
status: draft
visibility: global
formula: "LTV / CAC"
unit: ratio
---

# LTV:CAC Ratio

**Lead/Lag.** Leading indicator; measures whether unit economics support the current level
of growth investment. [Verified: ADR-004 §5]

**Interpretation.** Compares the lifetime value of a customer against the cost to acquire
them. A ratio ≥ 3 is a commonly cited threshold for healthy unit economics in subscription
and SaaS models, though the appropriate threshold varies by business model and growth stage.
[Verified: ADR-004 §5]

**Formula.** [[kpis/ltv|LTV]] / [[kpis/cac|CAC]].

**Data needs.** Requires both LTV and CAC inputs; see component KPI notes for data
requirements. [Verified: ADR-004 §5]

**Industry differences.** Benchmark thresholds vary materially by business model, growth
stage, and market. The ≥ 3 threshold is most commonly cited for venture-stage SaaS;
other models may operate at different viable ratios. [Verified: ADR-004 §5]

**Relevant domains.**
- [[domains/sales-and-marketing]]
- [[domains/revenue-growth]]

**Related frameworks.**
- [[frameworks/cac-ltv-analysis]] — primary framework for LTV:CAC decomposition and diagnosis
- [[frameworks/funnel-gtm-economics]] — links GTM efficiency metrics to the LTV:CAC outcome

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
