"""Scenario Evaluator (ADR-010 Phase 3) — reuses P1's ledger arithmetic.

Deciding WHICH scenarios matter (a bull/base/bear split, or something
case-specific) is still consulting judgment — an LLM proposes named
:class:`~app.pipeline.consulting_schema.ScenarioAssumption` objects, each a
set of assumption-value overrides. Evaluating each one's NUMERIC consequence
is mechanical: the ledger is re-evaluated under each override set with the
exact same arithmetic path ``sensitivity_analysis.py`` and the Quant Gate
itself use. No scenario's derived outcome is ever the LLM's own narrated
number — it is computed, exactly as a single derived ledger value always is.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from app.pipeline.consulting_schema import ScenarioAssumption
from app.pipeline.quantcheck import Entry
from app.pipeline.sensitivity_analysis import recompute_all


@dataclass(frozen=True)
class ScenarioOutcome:
    scenario_id: str
    label: str
    values: Mapping[str, Decimal]  # every entry id -> its value under this scenario
    probability: float | None = None
    narrative: str = ""


def evaluate_scenarios(
    entries: Mapping[str, Entry], scenarios: list[ScenarioAssumption]
) -> list[ScenarioOutcome]:
    """Recompute the full ledger under each named scenario's overrides.

    An override id that isn't a real ledger entry is simply ignored for that
    scenario (rather than raising) — the LLM proposing a scenario referencing
    a since-superseded id should not crash the analysis; it's caught instead
    by comparing ``ScenarioOutcome.values`` against ``entries`` downstream,
    the same fail-soft posture the whole reasoning layer takes toward
    LLM-declared references (ADR-010 §6b: proposals are judgment, verification
    is code's job — but a bad proposal degrades gracefully, it doesn't crash).
    """
    outcomes: list[ScenarioOutcome] = []
    for scenario in scenarios:
        overrides = {
            eid: value for eid, value in scenario.overrides.items() if eid in entries
        }
        values = recompute_all(entries, overrides)
        outcomes.append(
            ScenarioOutcome(
                scenario_id=scenario.scenario_id,
                label=scenario.label,
                values=values,
                probability=scenario.probability,
                narrative=scenario.narrative,
            )
        )
    return outcomes
