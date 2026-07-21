"""The reusable benchmark case library — the requester's "Case Library"
section: a small, real, immutable set of fixed cases spanning different
engagement types, company sizes, and difficulty levels.

Data-driven catalog, same pattern established in every prior layer (W8's
``catalog.py`` onward): a tuple of ``BenchmarkCase`` instances, ALL-KEYWORD
constructed — the same discipline adopted from W9 onward specifically to
make field-order-mismatch bugs (the real W8 bug) structurally impossible.

Every ``expected_frameworks`` entry below is a real key already registered
in ``app.knowledge.catalog``; every ``expected_deliverables`` entry a real
``DeliverableType``. Cases are deliberately few and real rather than many
and shallow — each is meant to be replayed end-to-end, not just listed.
"""

from __future__ import annotations

from app.consulting.models import EngagementCategory as EC
from app.deliverables.models import DeliverableType as DT
from app.knowledge.models import CompanySize as CS

from .models import BenchmarkCase, CaseDifficulty

CASES: tuple[BenchmarkCase, ...] = (
    BenchmarkCase(
        case_id="case-market-entry-saas-eu",
        title="Mid-market SaaS firm evaluating EU market entry",
        industry="Software (SaaS)",
        company_size=CS.MIDMARKET,
        region="North America -> European Union",
        engagement_type=EC.MARKET_ENTRY,
        difficulty=CaseDifficulty.MEDIUM,
        problem_statement=(
            "Our client, a North American B2B SaaS vendor, wants to know "
            "whether and how to enter the European Union market within "
            "the next 18 months."
        ),
        background=(
            "The client has $40M ARR domestically, a single product line, "
            "and no EU legal entity, sales team, or GDPR-compliant "
            "infrastructure today."
        ),
        available_data=(
            "domestic ARR and churn by segment",
            "industry analyst EU market-sizing report",
            "competitor pricing pages for 4 EU incumbents",
        ),
        ground_truth=(
            "Enter via a local channel partnership rather than a direct "
            "subsidiary, given the regulatory (GDPR) and go-to-market "
            "complexity relative to the client's balance sheet."
        ),
        expected_frameworks=(
            "pestle",
            "five_forces",
            "tam_sam_som",
            "swot",
            "dcf",
            "risk_matrix",
        ),
        expected_findings=(
            "EU TAM is large but fragmented across jurisdictions",
            "GDPR compliance is a binding constraint on direct entry timeline",
        ),
        expected_recommendations=("Enter the EU via a local channel partnership",),
        expected_deliverables=(DT.EXECUTIVE_SUMMARY, DT.BUSINESS_CASE),
        reference_sources=(
            "client-provided ARR/churn export",
            "third-party EU SaaS market report",
        ),
        tags=("market_entry", "saas", "gdpr"),
    ),
    BenchmarkCase(
        case_id="case-cost-reduction-manufacturing",
        title="Enterprise manufacturer cost-reduction program",
        industry="Industrial Manufacturing",
        company_size=CS.ENTERPRISE,
        region="United States",
        engagement_type=EC.COST_REDUCTION,
        difficulty=CaseDifficulty.HARD,
        problem_statement=(
            "Client's operating margin has compressed 400bps over two "
            "years; the board wants a structural cost-reduction plan, not "
            "a one-time cut."
        ),
        background=(
            "Three manufacturing plants, unionized workforce at one site, "
            "input costs up 18% while price increases have lagged."
        ),
        available_data=(
            "plant-level P&L for 3 years",
            "supplier contract terms for top 20 inputs",
            "headcount and overtime data by plant",
        ),
        ground_truth=(
            "Structural savings come primarily from supplier renegotiation "
            "and overtime reduction, not headcount cuts at the unionized "
            "site, which carries disproportionate execution risk."
        ),
        expected_frameworks=(
            "value_chain",
            "cost_structure_analysis",
            "profitability_analysis",
        ),
        expected_findings=(
            "Overtime costs at Plant B exceed industry benchmark by 30%",
            "Top 5 suppliers represent 60% of input spend with no recent renegotiation",
        ),
        expected_recommendations=(
            "Renegotiate top-5 supplier contracts before any headcount action",
        ),
        expected_deliverables=(DT.EXECUTIVE_SUMMARY, DT.OPERATIONAL_EXCELLENCE_REPORT),
        reference_sources=("client P&L exports", "supplier contract register"),
        tags=("cost_reduction", "manufacturing", "operations"),
    ),
    BenchmarkCase(
        case_id="case-due-diligence-startup-acquisition",
        title="Enterprise acquirer evaluating a startup acquisition target",
        industry="Enterprise Software",
        company_size=CS.STARTUP,
        region="United States",
        engagement_type=EC.DUE_DILIGENCE,
        difficulty=CaseDifficulty.HARD,
        problem_statement=(
            "Client is evaluating an acquisition of a 40-person startup "
            "and needs a go/no-go recommendation within 6 weeks."
        ),
        background=(
            "Target has $6M ARR, 140% net revenue retention, but customer "
            "concentration with the top 3 accounts at 45% of revenue."
        ),
        available_data=(
            "target's data room financials (2 years)",
            "customer cohort retention data",
            "cap table and key employee retention terms",
        ),
        ground_truth=(
            "Proceed, conditioned on retention agreements for the top 3 "
            "customer relationship owners and an earnout tied to customer "
            "concentration risk, not a straight all-cash deal."
        ),
        expected_frameworks=("dcf", "risk_matrix", "financial_benchmarking"),
        expected_findings=(
            "Revenue concentration in top 3 accounts is a material risk",
            "Net revenue retention of 140% is well above category benchmark",
        ),
        expected_recommendations=(
            "Proceed with an earnout structure tied to customer retention",
        ),
        expected_deliverables=(DT.DUE_DILIGENCE_REPORT, DT.INVESTMENT_COMMITTEE_MEMO),
        reference_sources=("target data room", "cohort retention analysis"),
        tags=("due_diligence", "m_and_a", "startup"),
    ),
    BenchmarkCase(
        case_id="case-digital-transformation-retail",
        title="Retail chain digital transformation roadmap",
        industry="Retail",
        company_size=CS.ENTERPRISE,
        region="United Kingdom",
        engagement_type=EC.DIGITAL_TRANSFORMATION,
        difficulty=CaseDifficulty.EASY,
        problem_statement=(
            "Client wants a phased digital transformation roadmap to "
            "close the e-commerce gap with digitally-native competitors."
        ),
        background=(
            "E-commerce is 12% of revenue versus a 35% category average; "
            "legacy POS and inventory systems limit omnichannel fulfillment."
        ),
        available_data=(
            "channel revenue mix by quarter",
            "IT systems inventory and vendor contracts",
        ),
        ground_truth=(
            "Sequence unified inventory visibility before customer-facing "
            "omnichannel features, since fulfillment promises cannot be "
            "kept without it."
        ),
        expected_frameworks=("digital_maturity", "technology_capability_assessment"),
        expected_findings=(
            "E-commerce share trails category average by 23 points",
            "Inventory systems lack real-time cross-channel visibility",
        ),
        expected_recommendations=(
            "Sequence a unified inventory platform ahead of omnichannel "
            "customer features",
        ),
        expected_deliverables=(DT.TRANSFORMATION_ROADMAP, DT.EXECUTIVE_SUMMARY),
        reference_sources=("client channel revenue export", "IT systems inventory"),
        tags=("digital_transformation", "retail"),
    ),
)


def all_benchmark_cases() -> tuple[BenchmarkCase, ...]:
    return CASES
