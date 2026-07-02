"""Enumerations for the Engagement State sections (ADR-002 §3–§25).

Open taxonomies include ``OTHER``/``UNKNOWN`` so new values can be introduced
without a breaking change (enums designed for extensibility).
"""

from __future__ import annotations

from enum import StrEnum


class CaseArchetype(StrEnum):
    """Consulting case archetype (ADR-002 §7 / ADR-004 §2 domains)."""

    PROFITABILITY = "profitability"
    REVENUE_GROWTH = "revenue_growth"
    COST_REDUCTION = "cost_reduction"
    PRICING = "pricing"
    MARKET_ENTRY = "market_entry"
    M_AND_A = "m_and_a"
    NEW_PRODUCT_LAUNCH = "new_product_launch"
    TURNAROUND = "turnaround"
    DIGITAL_TRANSFORMATION = "digital_transformation"
    SUPPLY_CHAIN = "supply_chain"
    ORGANIZATIONAL_DESIGN = "organizational_design"
    AI_STRATEGY = "ai_strategy"
    CORPORATE_STRATEGY = "corporate_strategy"
    CUSTOMER_STRATEGY = "customer_strategy"
    SALES_MARKETING = "sales_marketing"
    PE_DUE_DILIGENCE = "pe_due_diligence"
    GENERIC = "generic"
    UNKNOWN = "unknown"


class ObjectiveSource(StrEnum):
    CLIENT_STATED = "client_stated"
    INFERRED = "inferred"


class ConstraintType(StrEnum):
    BUDGET = "budget"
    TIME = "time"
    LEGAL = "legal"
    POLITICAL = "political"
    SCOPE = "scope"
    EXPLICIT_NO = "explicit_no"
    OTHER = "other"


class StakeholderRelationship(StrEnum):
    CLIENT = "client"
    AFFECTED = "affected"
    DECISION_MAKER = "decision_maker"
    BLOCKER = "blocker"
    OTHER = "other"


class GapCriticality(StrEnum):
    LOAD_BEARING = "load_bearing"
    USEFUL = "useful"
    MINOR = "minor"


class GapStatus(StrEnum):
    OPEN = "open"
    ASKED = "asked"
    ANSWERED = "answered"
    ASSUMED = "assumed"


class PlanStepStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"


class IssueNodeStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    ANSWERED = "answered"
    BLOCKED = "blocked"


class KnowledgeRefKind(StrEnum):
    FRAMEWORK = "framework"
    PLAYBOOK = "playbook"
    COMPANY_PROFILE = "company_profile"
    PRIOR_CASE = "prior_case"
    BENCHMARK = "benchmark"
    OTHER = "other"


class AnalysisStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    REWORKING = "reworking"


class ReviewCheckName(StrEnum):
    MECE = "mece"
    EVIDENCE_TRACEABLE = "evidence_traceable"
    CONSISTENCY = "consistency"
    CALIBRATION = "calibration"
    GAP_CLOSURE = "gap_closure"


class CheckResult(StrEnum):
    PASS = "pass"
    FAIL = "fail"


class ReviewVerdict(StrEnum):
    APPROVED = "approved"
    NEEDS_REWORK = "needs_rework"


class ChallengeVerdict(StrEnum):
    STANDS = "stands"
    STANDS_WITH_CAVEATS = "stands_with_caveats"
    NEEDS_REWORK = "needs_rework"


class RecommendationStatus(StrEnum):
    DRAFT = "draft"
    GATED = "gated"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class DeliverableKind(StrEnum):
    REPORT = "report"
    DECK = "deck"
    MODEL = "model"
    OTHER = "other"


class DeliverableStatus(StrEnum):
    PENDING = "pending"
    GENERATED = "generated"
    DELIVERED = "delivered"


class GateResult(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    LOOP = "loop"


class PendingKind(StrEnum):
    HUMAN_INPUT = "human_input"
    INFORMATION = "information"
    BLOCKER = "blocker"
    OTHER = "other"
