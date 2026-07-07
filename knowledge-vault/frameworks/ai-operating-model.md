---
id: fw_ai_op_model
type: framework
title: AI Operating Model
tags:
- framework
- supporting
source: ADR-004 §3 (Consulting Knowledge Library)
last_verified: '2026-07-07'
status: draft
visibility: global
name: AI Operating Model
domains:
- '[[domains/ai-strategy]]'
tier: supporting
purpose: Design the organizational model for AI — centers of excellence, embedded
  roles, governance, and ways of working.
when_to_use: When scaling AI from pilots to enterprise-wide deployment.
diagnostic_questions:
- Should AI governance be centralized, federated, or a hybrid hub-and-spoke model?
- Where are AI talent, tooling, and model approval decisions made?
success_metrics:
- AI use-case deployment rate (concepts to production)
- Time from concept to production
common_risks:
- A central CoE becoming a bottleneck while business units move ahead without governance
common_mistakes:
- Designing AI governance without defining who has authority to approve models for
  production use
related_frameworks:
- '[[frameworks/ai-use-case-portfolio]]'
version: '0.1'
---

# AI Operating Model

**Domain(s).** [[domains/ai-strategy]]

**Purpose.** Design the organizational model for AI — centers of excellence, embedded roles, governance, and ways of working.

**When to use.** When scaling AI from pilots to enterprise-wide deployment.

## Diagnostic questions
- Should AI governance be centralized, federated, or a hybrid hub-and-spoke model?
- Where are AI talent, tooling, and model approval decisions made?

## Success metrics
- AI use-case deployment rate (concepts to production)
- Time from concept to production

## Common risks
- A central CoE becoming a bottleneck while business units move ahead without governance

## Common mistakes
- Designing AI governance without defining who has authority to approve models for production use

## Related frameworks
- [[frameworks/ai-use-case-portfolio]]

> **Draft (AI-authored, unreviewed).** Promote to `approved` only after reviewer sign-off (Hybrid authorship, ADR-004).
