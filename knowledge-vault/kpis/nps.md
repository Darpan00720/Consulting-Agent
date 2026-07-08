---
id: kpi_nps
type: kpi
title: Net Promoter Score
aliases:
- NPS
tags:
- kpi
- customer-strategy
source: ADR-004 §5 (Consulting Knowledge Library)
last_verified: '2026-07-08'
status: draft
visibility: global
formula: "% Promoters - % Detractors"
unit: "score (range -100 to +100)"
---

# Net Promoter Score (NPS)

**Lead/Lag.** Leading indicator; correlates with future referral rates, expansion revenue,
and churn risk ahead of financial results. [Verified: ADR-004 §5]

**Interpretation.** Measures customer loyalty and advocacy propensity from a single
likelihood-to-recommend question. Promoters (9–10) expand the customer base through referral;
Detractors (0–6) create negative word-of-mouth. [Verified: ADR-004 §5]

**Formula.** % respondents scoring 9–10 (Promoters) − % respondents scoring 0–6 (Detractors).
Passives (7–8) are excluded from the calculation.

**Data needs.** Customer survey responses on a 0–10 likelihood-to-recommend scale, with
sufficient sample size and representative coverage across segments. [Verified: ADR-004 §5]

**Industry differences.** Benchmark norms differ significantly by sector; cross-industry
NPS comparisons are unreliable. Trend direction and within-industry peer comparison are
more meaningful than absolute score level. [Verified: ADR-004 §5]

**Relevant domains.**
- [[domains/customer-strategy]]

**Related frameworks.**
- [[frameworks/nps-loyalty-economics]] — links NPS to revenue economics (retention, expansion, referral)
- [[frameworks/customer-journey-mapping]] — identifies journey stages that drive promoter or detractor behaviour

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
