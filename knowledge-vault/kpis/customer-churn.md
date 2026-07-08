---
id: kpi_customer_churn
type: kpi
title: Customer Churn
aliases:
- Churn Rate
- Logo Churn
tags:
- kpi
- customer-strategy
- revenue-growth
source: ADR-004 §5 (Consulting Knowledge Library)
last_verified: '2026-07-08'
status: draft
visibility: global
formula: "Customers lost in period / Customers at period start"
unit: "%"
---

# Customer Churn

**Lead/Lag.** Leading indicator; a rising churn rate predicts future revenue decline before
it appears in top-line results. [Verified: ADR-004 §5]

**Interpretation.** The share of customers that ceased transacting in a defined period.
Directly feeds the churn input of [[kpis/ltv|LTV]]; also indicates retention and
relationship-management effectiveness. [Verified: ADR-004 §5]

**Formula.** Customers lost in period / Customers at the start of the period × 100.

**Data needs.** Customer count at start and end of period, with churned customers positively
identified (not merely inactive). Definition of "customer" must be held constant. [Verified: ADR-004 §5]

**Industry differences.** Logo churn (count of customers) and revenue churn (value of lost
ARR) can diverge significantly when customers vary in size. A business reporting low logo
churn may still face severe revenue churn if it is losing its largest accounts. [Verified: ADR-004 §5]

**Relevant domains.**
- [[domains/customer-strategy]]
- [[domains/revenue-growth]]

**Related frameworks.**
- [[frameworks/retention-economics]] — quantifies the revenue impact of reducing churn
- [[frameworks/cohort-retention-analysis]] — tracks churn patterns across acquisition cohorts over time
- [[frameworks/nps-loyalty-economics]] — links NPS survey scores to predicted churn behaviour

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
