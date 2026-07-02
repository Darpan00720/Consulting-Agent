"""Shared read-only helpers for validators (pure lookups, not orchestration)."""

from __future__ import annotations

from collections.abc import Sequence

from common.models import DomainObject
from state.models import EngagementState
from state.sections.analysis import AnalysisBlock
from state.sections.enums import GateResult

_ANALYSIS_ATTRS = (
    "financial_analysis",
    "market_analysis",
    "operations_analysis",
    "strategy_analysis",
    "risk_analysis",
)


def analysis_blocks(state: EngagementState) -> list[tuple[str, AnalysisBlock]]:
    """Return (attribute-name, block) for each populated analysis section."""
    blocks: list[tuple[str, AnalysisBlock]] = []
    for attr in _ANALYSIS_ATTRS:
        block = getattr(state, attr)
        if block is not None:
            blocks.append((attr, block))
    return blocks


def id_set(items: Sequence[DomainObject]) -> set[str]:
    """The set of ids in a collection of domain objects."""
    return {item.id for item in items}


def has_pass_gate(state: EngagementState, gate: str) -> bool:
    """Whether a named quality gate has a recorded PASS result."""
    return any(
        g.gate == gate and g.result is GateResult.PASS for g in state.quality_gates
    )
