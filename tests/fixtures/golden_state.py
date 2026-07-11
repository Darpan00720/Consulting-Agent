"""Golden-state factory for StratAgent integration tests (M7/M8).

``make_golden_profitability_state`` returns a fully-populated ``EngagementState``
representing a completed profitability engagement.  Every claim carries evidence
or an assumption ref; both governance gates are cleared.  The state is designed
so that ``render_report`` and ``check_render_ready`` produce deterministic output
with no warnings.
"""

from __future__ import annotations

from state.enums import LifecycleStatus
from state.identifiers import AssumptionId, EngagementId, EvidenceId, IssueNodeId
from state.ledgers import Assumption, AssumptionStatus, Evidence, EvidenceType
from state.models import EngagementMetadata, EngagementState
from state.sections.analysis import AnalysisBlock, Finding, SensitivityCase
from state.sections.enums import (
    AnalysisStatus,
    CaseArchetype,
    ChallengeVerdict,
    CheckResult,
    ConstraintType,
    IssueNodeStatus,
    KnowledgeRefKind,
    ObjectiveSource,
    ReviewCheckName,
    ReviewVerdict,
    StakeholderRelationship,
)
from state.sections.governance import ChallengeNotes, ReviewCheck, ReviewerNotes
from state.sections.output import (
    ConfidenceReport,
    NextStep,
    Recommendations,
    RejectedAlternative,
)
from state.sections.planning import (
    FrameworkSelection,
    IssueNode,
    KnowledgeReference,
)
from state.sections.scoping import (
    CaseClassification,
    Constraint,
    Objective,
    ProblemDefinition,
    Stakeholder,
)

# Fixed IDs for determinism
_EV_REVENUE = EvidenceId("ev_revenue_001")
_EV_COST = EvidenceId("ev_cost_001")
_EV_MARKET = EvidenceId("ev_market_001")
_ASSUM_GROWTH = AssumptionId("assum_growth_001")
_NODE_ROOT = IssueNodeId("node_root")
_NODE_REVENUE = IssueNodeId("node_revenue")
_NODE_COST = IssueNodeId("node_cost")
_NODE_PRICE = IssueNodeId("node_price")
_NODE_VOLUME = IssueNodeId("node_volume")
_NODE_COGS = IssueNodeId("node_cogs")
_NODE_OPEX = IssueNodeId("node_opex")


def make_golden_profitability_state() -> EngagementState:
    """Return a complete, governance-cleared EngagementState for a profitability case.

    Suitable for render_report, check_render_ready, and consistency validation.
    All assertions carry evidence_refs or assumption_refs.
    Both reviewer (approved) and challenger (stands) verdicts are set.
    """
    # --- Evidence ledger ---
    ev_revenue = Evidence(
        id=_EV_REVENUE,
        claim="Net revenue declined 12% YoY from $200M to $176M.",
        type=EvidenceType.CLIENT_FACT,
        confidence=0.95,
        validated=True,
        validator="financial-analyst",
    )
    ev_cost = Evidence(
        id=_EV_COST,
        claim="COGS increased 8% in absolute terms due to raw-material inflation.",
        type=EvidenceType.CLIENT_FACT,
        confidence=0.90,
        validated=True,
        validator="financial-analyst",
    )
    ev_market = Evidence(
        id=_EV_MARKET,
        claim="Industry peers show average margin compression of 4pp in same period.",
        type=EvidenceType.EXTERNAL_SOURCE,
        source="IBISWorld Industry Report 2025-Q4",
        confidence=0.75,
        validated=False,
    )

    # --- Assumption ledger ---
    assum_growth = Assumption(
        id=_ASSUM_GROWTH,
        statement="Market volume will recover to 2023 levels within 18 months.",
        value="Volume +10% over 18 months",
        rationale=(
            "Industry analyst consensus (IBISWorld 2025-Q4); "
            "management corroborated in kickoff session."
        ),
        owner="market-analyst",
        confidence=0.65,
        load_bearing=True,
        breakeven=(
            "If volume recovery is <+5% (vs assumed +10%), "
            "the revenue-led fix is insufficient and cost action becomes primary."
        ),
        status=AssumptionStatus.ACTIVE,
    )

    # --- Issue tree ---
    root = IssueNode(
        question="Why has operating profit declined by 18pp over the past 12 months?",
        owner=None,
        status=IssueNodeStatus.ANSWERED,
        answer=(
            "Both a revenue shortfall (−12% YoY) and cost inflation (+8% COGS) "
            "contributed, each accounting for roughly half of the margin compression."
        ),
        confidence=0.85,
    ).model_copy(update={"id": _NODE_ROOT})

    node_revenue = IssueNode(
        question="Is the profit decline driven primarily by a revenue shortfall?",
        owner="financial-analyst",
        status=IssueNodeStatus.ANSWERED,
        answer=(
            "Yes — revenue fell 12% YoY; "
            "price erosion (−7pp) dominated volume (−5pp)."
        ),
        confidence=0.90,
        evidence_refs=[_EV_REVENUE],
    ).model_copy(update={"id": _NODE_REVENUE, "parent": _NODE_ROOT})

    node_cost = IssueNode(
        question="Is the profit decline driven primarily by cost inflation?",
        owner="financial-analyst",
        status=IssueNodeStatus.ANSWERED,
        answer="Partially — COGS rose 8%; OPEX held flat as % revenue.",
        confidence=0.88,
        evidence_refs=[_EV_COST],
    ).model_copy(update={"id": _NODE_COST, "parent": _NODE_ROOT})

    node_price = IssueNode(
        question="Is average selling price declining?",
        owner="financial-analyst",
        status=IssueNodeStatus.ANSWERED,
        answer="Yes — ASP fell 7% driven by competitive discounting.",
        confidence=0.85,
        evidence_refs=[_EV_REVENUE],
    ).model_copy(update={"id": _NODE_PRICE, "parent": _NODE_REVENUE})

    node_volume = IssueNode(
        question="Is unit volume declining?",
        owner="market-analyst",
        status=IssueNodeStatus.ANSWERED,
        answer=(
            "Yes — volume down 5%; "
            "peer average is −3%, so relative underperformance."
        ),
        confidence=0.75,
        evidence_refs=[_EV_MARKET],
    ).model_copy(update={"id": _NODE_VOLUME, "parent": _NODE_REVENUE})

    node_cogs = IssueNode(
        question="What is driving COGS inflation?",
        owner="operations-analyst",
        status=IssueNodeStatus.ANSWERED,
        answer="Raw material (steel +22%) and logistics (+14%) dominate COGS increase.",
        confidence=0.88,
        evidence_refs=[_EV_COST],
    ).model_copy(update={"id": _NODE_COGS, "parent": _NODE_COST})

    node_opex = IssueNode(
        question="Is OPEX growth outpacing revenue?",
        owner="operations-analyst",
        status=IssueNodeStatus.ANSWERED,
        answer="No — OPEX grew 2% vs. −12% revenue; as a % of revenue OPEX rose 4pp.",
        confidence=0.90,
        evidence_refs=[_EV_COST],
    ).model_copy(update={"id": _NODE_OPEX, "parent": _NODE_COST})

    issue_tree = [
        root,
        node_revenue,
        node_cost,
        node_price,
        node_volume,
        node_cogs,
        node_opex,
    ]

    # --- Frameworks ---
    fw_profit = FrameworkSelection(
        name="Profit Tree (Revenue × Cost Decomposition)",
        archetype=CaseArchetype.PROFITABILITY,
        rationale=(
            "Standard profitability diagnostic — decomposes margin by revenue driver "
            "and cost driver to isolate root causes."
        ),
        adaptation=(
            "Extended to include peer-benchmarking leg "
            "given competitive discounting signal."
        ),
        source_ref="knowledge-vault/frameworks/profitability-analysis.md",
    )

    # --- Analysis blocks ---
    financial_block = AnalysisBlock(
        owner="financial-analyst",
        findings=[
            Finding(
                question="What is the magnitude of the revenue decline?",
                answer=(
                    "Revenue fell 12% YoY (from $200M to $176M); "
                    "price −7pp, volume −5pp."
                ),
                evidence_refs=[_EV_REVENUE],
                confidence=0.95,
                method="YoY delta from audited P&L",
            ),
            Finding(
                question="What is the EBITDA margin impact?",
                answer="EBITDA margin compressed 18pp (from 24% to 6%).",
                evidence_refs=[_EV_REVENUE, _EV_COST],
                confidence=0.92,
                method="Derived from revenue and cost actuals",
            ),
            Finding(
                question="What is the breakeven volume at current pricing?",
                answer=(
                    "[ASSUMPTION: Breakeven at ~$155M revenue "
                    "(12% below 2025 actuals); achievable if volume recovers 10%.]"
                ),
                assumption_refs=[_ASSUM_GROWTH],
                confidence=0.65,
                method="Contribution-margin breakeven model",
            ),
        ],
        sensitivity=[
            SensitivityCase(
                driver="Volume recovery",
                base="+10% over 18 months",
                stress="+5% over 18 months",
                effect="EBITDA margin 10% vs. 14% base case",
            )
        ],
        status=AnalysisStatus.COMPLETE,
    )

    market_block = AnalysisBlock(
        owner="market-analyst",
        findings=[
            Finding(
                question="Is market volume decline structural or cyclical?",
                answer="Cyclical — peer recovery expected H2 2026 per IBISWorld.",
                evidence_refs=[_EV_MARKET],
                confidence=0.70,
                method="IBISWorld trend analysis",
            ),
        ],
        status=AnalysisStatus.COMPLETE,
    )

    # --- Recommendations ---
    recommendations = Recommendations(
        decision=(
            "Prioritise pricing recovery over cost-cutting: "
            "implement selective price increases of 4–6% and reduce discounting, "
            "while accelerating COGS mitigation through supplier renegotiation."
        ),
        rationale=(
            "Revenue has the higher leverage (−12% vs. +8% cost), and market volume "
            "is expected to recover cyclically. Cost action alone cannot restore "
            "the 18pp margin gap without revenue recovery. The two levers are "
            "complementary, not alternatives."
        ),
        next_steps=[
            NextStep(
                step="Re-price bottom quartile SKUs by 4% effective Q1 2026.",
                sequence=1,
            ),
            NextStep(
                step="Renegotiate top-3 steel contracts using volume commitment.",
                sequence=2,
            ),
            NextStep(
                step="Establish monthly margin bridge review with CFO office.",
                sequence=3,
                depends_on=["step_1", "step_2"],
            ),
        ],
        alternatives_rejected=[
            RejectedAlternative(
                option="Across-the-board headcount reduction",
                why_not=(
                    "OPEX is not the primary driver; cuts would degrade "
                    "delivery capability during volume recovery."
                ),
            ),
        ],
    )

    # --- Reviewer notes ---
    reviewer_notes = ReviewerNotes(
        checks=[
            ReviewCheck(name=ReviewCheckName.MECE, result=CheckResult.PASS),
            ReviewCheck(
                name=ReviewCheckName.EVIDENCE_TRACEABLE, result=CheckResult.PASS
            ),
            ReviewCheck(name=ReviewCheckName.CONSISTENCY, result=CheckResult.PASS),
            ReviewCheck(name=ReviewCheckName.CALIBRATION, result=CheckResult.PASS),
            ReviewCheck(name=ReviewCheckName.GAP_CLOSURE, result=CheckResult.PASS),
        ],
        verdict=ReviewVerdict.APPROVED,
        issues=[],
    )

    # --- Challenger notes ---
    challenge_notes = ChallengeNotes(
        loadbearing_test=(
            "Load-bearing assumption: market volume recovers +10% in 18 months. "
            "Tested against IBISWorld pessimistic scenario (−2%): "
            "in that case revenue recovery stalls and cost action must be primary. "
            "Breakeven threshold is +5%; below that the recommendation inverts."
        ),
        counter_case=(
            "The strongest counter-case: pricing increases accelerate volume loss "
            "beyond the assumed 5%, deepening the revenue hole rather than closing it. "
            "Historical price elasticity estimates are limited to one IBISWorld source."
        ),
        what_would_change=[
            (
                "If price elasticity > 1.2 (currently assumed 0.8), "
                "price increases are net-negative."
            ),
            (
                "If volume recovery is < +5% in 18 months, "
                "cost reduction becomes primary lever."
            ),
            (
                "If a competitor matches price increases within 30 days, "
                "volume risk is reduced."
            ),
        ],
        verdict=ChallengeVerdict.STANDS_WITH_CAVEATS,
    )

    # --- Confidence report ---
    confidence = ConfidenceReport(
        by_section={
            "financial_analysis": 0.92,
            "market_analysis": 0.70,
        },
        overall=0.82,
        method="Weighted average by section evidence quality",
        drivers=[
            "Strong client-fact evidence for revenue and cost actuals.",
            (
                "Moderate confidence on market recovery assumption "
                "(single external source)."
            ),
        ],
    )

    # --- Knowledge references ---
    kr = KnowledgeReference(
        kind=KnowledgeRefKind.FRAMEWORK,
        vault_path="knowledge-vault/frameworks/profitability-analysis.md",
        query="profitability margin decline decomposition",
        relevance=0.92,
    )

    return EngagementState(
        metadata=EngagementMetadata(
            engagement_id=EngagementId("eng_golden_profitability"),
            tenant_id="tenant_acme",
            slug="acme-profitability-2025",
        ),
        status=LifecycleStatus.COMPLETED,
        problem=ProblemDefinition(
            raw_input=(
                "Our operating profit has fallen dramatically over the past year. "
                "Revenue is down and costs are up. We need to understand why and "
                "what to do about it. The board wants a clear answer by end of Q4."
            ),
            real_question=(
                "Why has operating profit declined 18pp in 12 months, "
                "and what is the fastest path to margin recovery?"
            ),
        ),
        objectives=[
            Objective(
                statement="Restore EBITDA margin to ≥15% within 18 months.",
                metric="EBITDA margin %",
                target="≥15%",
                priority=1,
                source=ObjectiveSource.CLIENT_STATED,
            ),
        ],
        constraints=[
            Constraint(
                statement=(
                    "No headcount reductions in production without board approval."
                ),
                type=ConstraintType.POLITICAL,
                hard=True,
            ),
        ],
        stakeholders=[
            Stakeholder(
                name_or_role="CFO",
                relationship=StakeholderRelationship.DECISION_MAKER,
                interest="Margin recovery trajectory and quarterly milestone gates.",
            ),
        ],
        classification=CaseClassification(
            primary_archetype=CaseArchetype.PROFITABILITY,
            confidence=0.95,
            rationale=(
                "Revenue and cost drivers explicitly cited; "
                "margin gap is the core diagnostic."
            ),
        ),
        assumptions=[assum_growth],
        evidence=[ev_revenue, ev_cost, ev_market],
        frameworks=[fw_profit],
        issue_tree=issue_tree,
        knowledge_references=[kr],
        financial_analysis=financial_block,
        market_analysis=market_block,
        reviewer_notes=reviewer_notes,
        challenge_notes=challenge_notes,
        recommendations=recommendations,
        confidence=confidence,
    )
