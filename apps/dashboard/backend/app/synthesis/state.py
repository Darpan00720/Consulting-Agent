"""``SynthesisState`` — the mutable container the Synthesis Engine builds up
on top of a REAL ``app.consulting.state.EngagementState`` (never a copy of
its evidence — a live reference, so evidence added to the engagement after
synthesis begins is immediately visible here too).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.consulting.state import EngagementState
from app.synthesis.models import (
    BusinessImpactAssessment,
    Finding,
    ImplementationTheme,
    Insight,
    Opportunity,
    Recommendation,
    RootCauseAnalysis,
    StrategicNarrative,
    TradeOffResult,
)


@dataclass
class SynthesisState:
    engagement_state: EngagementState
    findings: dict[str, Finding] = field(default_factory=dict)
    insights: dict[str, Insight] = field(default_factory=dict)
    opportunities: dict[str, Opportunity] = field(default_factory=dict)
    recommendations: dict[str, Recommendation] = field(default_factory=dict)
    implementation_themes: dict[str, ImplementationTheme] = field(default_factory=dict)
    narratives: dict[str, StrategicNarrative] = field(default_factory=dict)
    root_cause_analyses: dict[str, RootCauseAnalysis] = field(default_factory=dict)
    business_impact_assessments: dict[str, BusinessImpactAssessment] = field(
        default_factory=dict
    )
    trade_off_results: list[TradeOffResult] = field(default_factory=list)
