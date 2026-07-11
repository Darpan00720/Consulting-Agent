# StratAgent — GA (v1.0) Release Checklist

Concrete items that must be **done and verified** before General Availability.
Grouped by area. Each item has an owner and an objective check. Drawn from the
research-evaluation "before GA" recommendations plus standard launch hygiene.

Legend: ☐ open · ☑ done · ⛔ blocker (GA cannot ship while open).

---

## A. Evidence & correctness (the core gap)
- ⛔ **Evidence Provider populated.** At least one sourced provider (benchmarks/
  comparables/market data) attached via the ADR-007 seam, so numbers can be
  sourced rather than only assumed. *Or* an explicit, signed decision that GA
  ships assumption-only with prominent labeling. (Beta answers which.)
- ⛔ **Zero unresolved hallucinations.** Every confirmed fabrication from beta
  root-caused and fixed; a regression test added.
- ☐ Determinism study run (same case ×k): recommendation-stability and
  score-variance documented; user-facing guidance written.
- ☐ Assumption-ledger completeness check on by every report (already enforced by
  the live gate; confirm it fires in the GA flow).

## B. Quality evidence
- ⛔ ≥ 90 completed beta engagements analyzed; quality distributions published.
- ☐ Usefulness median ≥ 5 and confidence median ≥ 5 (M2/M3) met.
- ☐ Per-archetype quality reported; any archetype < 5 median flagged with a plan
  (e.g., document as "supported with caution").
- ☐ Baseline comparison re-confirmed at beta scale (StratAgent > single-shot).

## C. Governance & pipeline
- ☑ Mandatory Reviewer + Challenger in every mode (RC1.2 / ADR-006).
- ☑ Live validation gate blocks report delivery on failure (RC1.2).
- ☐ Gate + governance verified on the full GA engagement flow (not just fixtures).
- ☐ Rework-loop bound confirmed (max cycles; escalates to human, never loops).

## D. Safety, ethics, legal
- ⛔ Appropriate-use / prohibited-use policy shipped in-product (not just docs).
- ⛔ Mandatory human-review affordance: report clearly states "review every number;
  you own the recommendation."
- ☐ Prohibited-use guardrails: regulated finance/legal/medical, live trading,
  irreversible high-stakes — detection or explicit disclaimer at intake.
- ☐ Privacy review: what client data users paste is stored/logged where; retention
  + deletion policy; tenant isolation confirmed.
- ☐ Security review of file I/O and any provider connectors.

## E. Reliability & ops
- ☐ Latency characterized (p50/p90 per engagement) and surfaced to users.
- ☐ Cost per engagement measured; pricing/usage limits defined.
- ☐ Failure handling: partial-engagement recovery; clear error surfaced, never a
  silent stop.
- ☐ Observability: engagement traces, gate outcomes, and errors are logged.

## F. Documentation & support
- ☐ User guide, quickstart, appropriate-use, and "how to read a report" published.
- ☐ Developer guide current (packages, gate, providers).
- ☐ Known-limitations page (assumptions-not-facts, non-determinism, no live data).
- ☐ Support path + issue intake for GA users.

## G. Repository hygiene
- ☐ RC1.2 changes committed; version tag set.
- ☐ ruff / black / mypy / pytest green on the release commit.
- ☐ CHANGELOG + release notes finalized.

---

**GA may proceed only when every ⛔ blocker is ☑ and the
[Go/No-Go Framework](Go-No-Go-Framework.md) returns GO.**
