# Framework Library Migration — RC1.2 Convergence

**Status:** the plugin's `knowledge/frameworks/*.md` archetype cheat sheets are
**deprecated** as of RC1.2. The single authoritative framework source is now the
**governed knowledge vault** at `knowledge-vault/frameworks/` (ADR-003 / ADR-004),
which holds 60+ typed framework notes with frontmatter (`type`, `domains`,
`when_to_use`, `diagnostic_questions`, `success_metrics`).

## Why

RC1 validation (WI-1) found the classifier and the framework-selector reading
*different* framework stores with divergent coverage. This file records the
convergence to one source of truth.

## What changed

- **Source of truth:** `knowledge-vault/frameworks/` (canonical). All framework
  *content* lives here and nowhere else.
- **Retrieval:** all agents obtain frameworks by querying the vault through the
  Knowledge Agent / `knowledge.retrieve(...)` (default `vault_dir=knowledge-vault`),
  which routes by archetype using each note's `domains`/`tags`/`when_to_use` fields.
- **These 9 files** (`cost-reduction.md`, `growth.md`, `ma-acquisition.md`,
  `market-entry.md`, `new-product-launch.md`, `pricing.md`, `profitability.md`,
  `turnaround.md`, `generic-diagnose-recommend.md`) are now **redirect stubs**.
  They resolve (backwards compatibility) but carry no framework content.

## Archetype → vault framework routing (single index)

Use this only as a hint for which vault notes are typically relevant; the
retrieval adapter will rank them for the specific question.

| Archetype | Representative vault framework notes (`knowledge-vault/frameworks/`) |
|---|---|
| profitability | profit-tree · contribution-margin-analysis · segment-pl-analysis · cost-decomposition-benchmarking |
| cost-reduction | zero-based-budgeting · activity-based-costing · cost-to-serve-analysis · cost-decomposition-benchmarking · lever-prioritization |
| growth | growth-driver-tree · three-horizons · core-adjacency-expansion · bcg-growth-share-matrix |
| market-entry | market-attractiveness-right-to-win · tam-sam-som · beachhead-strategy · build-buy-partner |
| ma-acquisition | synergy-valuation · accretion-dilution-analysis · comparable-multiples · discounted-cash-flow · post-merger-integration · quality-of-earnings |
| pricing | value-based-pricing · price-elasticity-analysis · price-segmentation · van-westendorp · conjoint-analysis |
| new-product-launch | jobs-to-be-done · launch-economics-gtm · stage-gate · funnel-gtm-economics |
| turnaround | hundred-day-plan · zero-based-budgeting · cost-decomposition-benchmarking |
| generic-diagnose-recommend | profit-tree · porters-five-forces · mckinsey-7s · playing-to-win |
| org-redesign / operating-model | operating-model-spans-layers · raci-decision-rights · mckinsey-7s · channel-mix-optimization |
| digital-transformation | digital-maturity-value-feasibility · value-chain-digitization · product-agile-operating-model |
| supply-chain | scor-network-optimization · inventory-optimization · resilience-mapping · sales-operations-planning |
| customer-experience | customer-journey-mapping · nps-loyalty-economics · cohort-retention-analysis · retention-economics |
| due-diligence | quality-of-earnings · commercial-dd-value-creation · comparable-multiples · exit-analysis |
| product-strategy | jobs-to-be-done · stage-gate · core-adjacency-expansion |

> The vault covers several archetypes (org-redesign, digital-transformation,
> supply-chain, customer-experience, due-diligence, product-strategy) that never
> had a plugin cheat sheet — another reason the vault is the single source.

## Backwards compatibility

The 9 stub files remain at their original paths so any existing reference
resolves. New code and agents should query the vault directly.
