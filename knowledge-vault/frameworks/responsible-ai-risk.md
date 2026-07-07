---
id: fw_responsible_ai
type: framework
title: Responsible AI Risk Framework
tags:
- framework
- supporting
source: ADR-004 §3 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
name: Responsible AI Risk Framework
domains:
- '[[domains/ai-strategy]]'
tier: supporting
purpose: Identify and mitigate ethical, legal, and operational risks from AI deployments
  including bias, fairness, explainability, and regulatory compliance.
when_to_use: For every AI use case before production deployment, especially in regulated
  or customer-facing contexts.
diagnostic_questions:
- What is the failure mode and who is harmed if the model produces an incorrect output?
- Is the model's output explainable and auditable for regulatory or operational purposes?
success_metrics:
- Risk assessment completion rate (% of use cases)
- Bias test pass rate
- Regulatory compliance score
common_risks:
- Discovering regulatory non-compliance post-deployment, requiring costly remediation
common_mistakes:
- Treating responsible AI as a one-time checklist rather than an ongoing governance
  process
related_frameworks:
- '[[frameworks/ai-use-case-portfolio]]'
version: '0.1'
---

# Responsible AI Risk Framework

**Domain(s).** [[domains/ai-strategy]]

**Purpose.** Identify and mitigate ethical, legal, and operational risks from AI deployments including bias, fairness, explainability, and regulatory compliance.

**When to use.** For every AI use case before production deployment, especially in regulated or customer-facing contexts.

## Diagnostic questions
- What is the failure mode and who is harmed if the model produces an incorrect output?
- Is the model's output explainable and auditable for regulatory or operational purposes?

## Success metrics
- Risk assessment completion rate (% of use cases)
- Bias test pass rate
- Regulatory compliance score

## Common risks
- Discovering regulatory non-compliance post-deployment, requiring costly remediation

## Common mistakes
- Treating responsible AI as a one-time checklist rather than an ongoing governance process

## Related frameworks
- [[frameworks/ai-use-case-portfolio]]

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
