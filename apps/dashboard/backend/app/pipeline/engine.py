"""The engagement engine — runs the StratAgent lifecycle over the Claude API.

Mirrors the orchestrator skill's phase order:

    classify -> gap_analysis -> planning -> framing -> issue_tree
    -> analysis (5 analysts in parallel) -> review -> challenge -> reporting

Each phase is one Claude call using the plugin's agent markdown as the system
prompt. Governance is mandatory: reviewer and challenger always run before
report-writer (ADR-006). Progress is persisted as events and pushed to SSE
subscribers via the in-memory bus.
"""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any

from app import config, db
from app.events import bus
from app.pipeline import prompts
from app.pipeline.claude import call_agent, friendly_error

CallAgent = Callable[..., Awaitable[str]]


def _reviewer_verdict(text: str) -> str:
    """Extract 'approved' | 'needs_rework' from the reviewer's markdown.

    Prefers a verdict-context match; falls back to a bare token; defaults to
    'approved' when neither is present so a parse failure never blocks forever.
    """
    low = text.lower()
    m = re.search(r"verdict[^\n]{0,40}?(needs[_ ]rework|approved)", low)
    if m:
        return "needs_rework" if "rework" in m.group(1) else "approved"
    if re.search(r"needs[_ ]rework", low):
        return "needs_rework"
    return "approved"


def _challenger_verdict(text: str) -> str:
    """Extract 'stands' | 'stands_with_caveats' | 'needs_rework' (order matters
    since 'stands_with_caveats' contains 'stands'). Defaults permissively."""
    low = text.lower()
    m = re.search(
        r"verdict[^\n]{0,40}?(needs[_ ]rework|stands[_ ]with[_ ]caveats|stands)", low
    )
    token = m.group(1) if m else None
    if token is None:
        if re.search(r"needs[_ ]rework", low):
            token = "needs_rework"
        elif re.search(r"stands[_ ]with[_ ]caveats", low):
            token = "stands_with_caveats"
        elif "stands" in low:
            token = "stands"
    if token is None:
        return "stands_with_caveats"
    if "rework" in token:
        return "needs_rework"
    if "caveat" in token:
        return "stands_with_caveats"
    return "stands"

ANALYSTS = [
    "financial-analyst",
    "market-analyst",
    "operations-analyst",
    "strategy-analyst",
    "risk-analyst",
]

PHASES = [
    ("classify", "case-classifier"),
    ("gap_analysis", "information-gap"),
    ("planning", "planner"),
    ("framing", "framework-selector"),
    ("issue_tree", "issue-tree-generator"),
    ("analysis", "5 specialist analysts"),
    ("reconcile", "engagement-manager"),
    ("review", "reviewer"),
    ("challenge", "challenger"),
    ("reporting", "report-writer"),
]

# The Engagement Manager reconciliation step. The five analysts run in parallel
# and each mints its own assumption IDs and numbers, so they collide (two
# analysts both grab "AL-10"; financial and ops disagree on a synergy). A real
# EM harmonizes this into ONE canonical ledger before review. This system prompt
# is orchestration logic, not a consulting specialist, so it lives here rather
# than in agents/*.md.
ENGAGEMENT_MANAGER_SYSTEM = """You are the Engagement Manager on a McKinsey-style
consulting team. Five specialist analysts (financial, market, operations,
strategy, risk) worked in parallel and each wrote its own findings with its own
assumption IDs and its own numbers. Your job is NOT to redo their analysis — it
is to RECONCILE it into a single, internally consistent factbase that will pass
quality review.

Produce a CANONICAL RECONCILIATION with exactly these parts, in markdown:

## Canonical assumption ledger
One table, globally unique IDs (A1, A2, …). RENUMBER every analyst-local ID
(AL-1, A-001, "AL-1 (strategy)", etc.) into this single A-n sequence — the final
ledger must contain exactly one ID scheme with no suffixes or per-analyst
namespaces. Every load-bearing assumption appears ONCE. When two analysts
defined the same figure differently (e.g. both used "AL-10", or financial said
cost synergy $30M while operations said $15M), you MUST pick ONE authoritative
value and state why (prefer the more conservative / better-sourced figure; a
hard operational ceiling beats an optimistic estimate).
Columns: ID | Value | Confidence | Owner | Breakeven (what would flip it).

## Reconciled key figures
A short table of the decision-critical derived numbers, each with ONE value
computed consistently from the canonical ledger above: e.g. net synergy, the
value-creating price/premium ceiling, NPV at the expected price, the walk-away
price. If the analysts disagreed, compute the single authoritative number here
and note which analyst figure it supersedes.
NO CIRCULAR VALUATIONS: every valuation must be derived from its INPUTS
(cash flows, growth, margin, discount rate) — never back-solved from its own
breakeven, from the offer being evaluated, or from the conclusion it is meant
to test. If an analyst's "intrinsic value" was reverse-engineered from the
deal multiple or a breakeven threshold, mark it OPEN ("no independent
valuation exists") instead of laundering it into a figure.

## Options value comparison
One row per strategic option on a LIKE-FOR-LIKE basis: same horizon, same
discount rate, each valued as risk-adjusted value INCREMENTAL to the status quo
(doing nothing). Columns: Option | Risk-adjusted incremental value | Key driver
| Canonical IDs. Then one sentence naming which option has the highest number.
If an analyst's recommended option is NOT the highest-value row, do not change
the recommendation — but state the gap explicitly (e.g. "Option B recommended
despite €XM lower value; the offsetting factor claimed is Y, unquantified") so
the challenger and report-writer must confront it.

## Issue tree closure
One row per leaf question in the issue tree — this table is the authoritative
record of coverage (the tree's own status/answer fields are never updated).
Columns: Question (abbreviated) | Answer (one sentence, quantified) |
Status (answered / assumed) | Basis (canonical IDs, e.g. A3, A7).
Every leaf must appear. If no analyst addressed a leaf, close it from the
canonical ledger where possible and mark it "assumed"; if it genuinely cannot
be closed, mark it OPEN and state what evidence would close it.

## Corrections applied
A bullet list of every collision or contradiction you resolved (ID reused,
number in dispute, citation to a stale value) and how you resolved it.

Rules:
- Do NOT change any conclusion or recommendation — only harmonize IDs, numbers,
  and citations so there is a single source of truth.
- Never invent data. If a figure genuinely cannot be reconciled without new
  analysis, say so explicitly and mark it OPEN — do not paper over it.
- Preserve every value as a labeled assumption; never upgrade an assumption to a
  fact.
This canonical reconciliation supersedes any conflicting figure in the analyst
detail. Everything downstream (reviewer, challenger, report) treats it as the
single source of truth."""


async def _emit(engagement_id: str, event_type: str, payload: dict[str, Any]) -> None:
    seq = db.append_event(engagement_id, event_type, payload)
    await bus.publish(
        engagement_id,
        {"seq": seq, "type": event_type, "payload": payload, "created_at": time.time()},
    )


def _section(title: str, body: str) -> str:
    return f"\n\n# {title}\n\n{body.strip()}"


def _today() -> str:
    from datetime import date

    return date.today().isoformat()


def _standing_lessons() -> str:
    """Injected as guardrails into future engagements — the learning loop."""
    lessons = db.list_lessons()
    if not lessons:
        return ""
    body = "\n".join(f"- {row['text']}" for row in lessons)
    return _section(
        "Standing lessons from past engagements — apply these; do not repeat them",
        body,
    )


# The reflection step. After EVERY engagement, distil what the reviewer /
# challenger caught into DURABLE PROCESS lessons that guardrail future runs —
# the learning loop: each engagement makes the next one better.
# Hard anti-leakage guard: method only, never case facts — otherwise lessons
# would contaminate unrelated engagements.
REFLECTION_SYSTEM = """You extract DURABLE PROCESS LESSONS from a consulting
engagement's quality-review notes, to prevent the same class of mistake in
FUTURE, UNRELATED engagements.

Output 0 to 2 lessons, each on its own line, prefixed exactly `LESSON: `.

Each lesson MUST be a general methodological rule about HOW to run the analysis —
issue-tree coverage/MECE, assumption hygiene (unique IDs, breakevens),
reconciling figures across analysts, calibration, evidence discipline. It must
be transferable to any case in any industry.

STRICTLY FORBIDDEN (these would contaminate other engagements): company or
product names, any specific number or dollar figure, the case's conclusion, or
anything about this particular industry. If the only lessons you can find are
case-specific, output the single word NONE and nothing else.

Good: `LESSON: For acquisition cases, the issue tree must include a commercial /
go-to-market capability branch, not only R&D/product value.`
Bad (case-specific — never do this): `LESSON: BioFuture's pipeline is worth
$320M.`"""


def _parse_lessons(text: str) -> list[str]:
    out: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if line.upper().startswith("LESSON:"):
            lesson = line[len("LESSON:"):].strip()
            if lesson and lesson.upper() != "NONE":
                out.append(lesson[:400])
    return out


async def run_engagement(
    engagement_id: str,
    case_prompt: str,
    *,
    call: CallAgent = call_agent,
    api_key: str | None = None,
    model: str | None = None,
) -> None:
    """Run one full engagement. Persists status/report and emits events.

    ``api_key`` is the user's own key (BYOK); ``None`` uses server credentials.
    ``model`` overrides the default Claude model for every agent call.
    """
    db.set_engagement_status(engagement_id, "running")
    await _emit(engagement_id, "engagement_started", {"phases": [p for p, _ in PHASES]})
    outputs: dict[str, str] = {}

    async def phase(
        name: str,
        agent: str,
        user_message: str,
        *,
        system_override: str | None = None,
        **kw: Any,
    ) -> str:
        await _emit(engagement_id, "phase_started", {"phase": name, "agent": agent})
        started = time.monotonic()
        system = system_override or prompts.agent_system_prompt(agent)
        result = await call(agent, system, user_message, api_key=api_key, model=model, **kw)
        await _emit(
            engagement_id,
            "phase_completed",
            {
                "phase": name,
                "agent": agent,
                "duration_ms": round((time.monotonic() - started) * 1000),
                "output": result,
            },
        )
        return result

    try:
        case = f"# Case prompt\n\n{case_prompt.strip()}"
        # The learning loop: standing lessons from past engagements, injected as
        # guardrails so recurring errors are avoided this time.
        lessons = _standing_lessons()

        outputs["classify"] = await phase(
            "classify",
            "case-classifier",
            f"{case}\n\nProduce the structured intake brief.",
            max_tokens=2000,
        )

        outputs["gap_analysis"] = await phase(
            "gap_analysis",
            "information-gap",
            case
            + _section("Intake brief (case-classifier)", outputs["classify"])
            + "\n\nIdentify the load-bearing information gaps and seed the assumption "
            "ledger. This is a non-interactive run: for every gap, ASSUME with a "
            "labeled `[ASSUMPTION AL-xx: ...]` entry (statement, working value, "
            "confidence, breakeven) rather than escalating to a human.",
            max_tokens=2000,
        )

        outputs["planning"] = await phase(
            "planning",
            "planner",
            case
            + _section("Intake brief", outputs["classify"])
            + _section("Information gaps & assumption ledger", outputs["gap_analysis"])
            + "\n\nProduce the engagement plan.",
            max_tokens=1500,
        )

        outputs["framing"] = await phase(
            "framing",
            "framework-selector",
            case
            + _section("Intake brief", outputs["classify"])
            + _section("Assumption ledger", outputs["gap_analysis"])
            + _section(
                "Available frameworks (governed knowledge vault index)",
                prompts.vault_framework_index(),
            )
            + "\n\nSelect and adapt the primary and supporting frameworks from the "
            "index above. Name each selected framework exactly as it appears in "
            "the index.",
            max_tokens=1500,
        )

        # Retrieval: pull the FULL vault notes for the frameworks the selector
        # named, so downstream agents work from governed framework content
        # rather than the model's memory of it.
        framework_knowledge = prompts.selected_framework_notes(outputs["framing"])
        knowledge_section = (
            _section(
                "Selected framework notes (governed knowledge vault)",
                framework_knowledge,
            )
            if framework_knowledge
            else ""
        )

        outputs["issue_tree"] = await phase(
            "issue_tree",
            "issue-tree-generator",
            case
            + _section("Intake brief", outputs["classify"])
            + _section("Framework selection", outputs["framing"])
            + knowledge_section
            + lessons
            + "\n\nBuild the MECE issue tree with owned, testable leaves.\n\n"
            "If this is an acquisition / M&A / market-entry case, the tree MUST be "
            "complete on the standard commercial-due-diligence dimensions — omitting "
            "any of these is a MECE failure a partner would reject:\n"
            "1. Target asset value — what is being bought and what it's worth "
            "(pipeline/products, revenue & profit potential, likelihood of success).\n"
            "2. Target CAPABILITIES — R&D/technical capability and talent; "
            "intellectual property (patents, proprietary processes, know-how); AND the "
            "target's COMMERCIAL capability: sales, marketing, distribution channels, "
            "and customer / influencer / key-relationship access (e.g. key opinion "
            "leaders, regulators, major accounts). Do not analyse only the "
            "technical/product side — the go-to-market side is load-bearing.\n"
            "3. The target's existing partnerships or relationships (with competitors, "
            "customers, or other acquirers) that could constrain or change the deal.\n"
            "4. The ACQUIRER's own capability gaps the deal is meant to close, and "
            "whether it can integrate/realise them.\n"
            "5. Price, synergies, and valuation (does it create or destroy value?).\n"
            "6. Strategic ALTERNATIVES — other targets, partner vs build vs acquire, and "
            "not pursuing this move at all.\n"
            "7. Integration and execution risk.\n"
            "Assign each branch to the most appropriate owner; the market-analyst owns "
            "commercial-capability and go-to-market branches, not just market sizing.",
            max_tokens=3000,
        )

        # --- analysis: five specialists in SEQUENTIAL order -------------------
        # Groq free tier: 6 000 TPM. Each analyst call is ~3 000 tokens total
        # (1 000 input + 2 000 max output). The throttle in claude.py enforces
        # 65 s between calls, giving the bucket 6 500 token refill headroom.
        # Analysts run one-at-a-time (no semaphore needed) using MINIMAL context:
        # only case + key assumptions + issue tree — not all 5 prior outputs.
        await _emit(
            engagement_id,
            "phase_started",
            {"phase": "analysis", "agent": "5 specialist analysts"},
        )

        # Compact context for analysts: case + key assumptions + issue tree only.
        # This keeps analyst input ≤ 1 500 tokens (fits within 6 k TPM per call).
        analyst_base_context = (
            case
            + _section("Key assumptions & information gaps", outputs["gap_analysis"])
            + _section("Issue tree", outputs["issue_tree"])
            + knowledge_section
        )

        async def run_analyst(agent: str) -> tuple[str, str]:
            await _emit(engagement_id, "analyst_started", {"agent": agent})
            started = time.monotonic()
            result = await call(
                agent,
                prompts.agent_system_prompt(agent),
                analyst_base_context
                + f"\n\nAnswer only the issue-tree branches owned by the {agent}. "
                "Produce concise, quantified analysis. Label every assumption "
                "with a sequentially numbered ID: `[ASSUMPTION AL-1: ...]`, "
                "`[ASSUMPTION AL-2: ...]`, and so on — never output a literal "
                "placeholder like 'AL-xx'. Keep total response under 500 words.",
                api_key=api_key,
                model=model,
                max_tokens=2000,
            )
            await _emit(
                engagement_id,
                "analyst_completed",
                {"agent": agent, "duration_ms": round((time.monotonic() - started) * 1000)},
            )
            return agent, result

        # Run analysts sequentially to stay within Groq 6 k TPM.
        analyst_results: list[tuple[str, str]] = []
        for analyst_name in ANALYSTS:
            analyst_results.append(await run_analyst(analyst_name))
        analyst_outputs: dict[str, str] = {a: r for a, r in analyst_results}

        def render_analysis() -> str:
            return "\n\n".join(
                f"## {a}\n\n{analyst_outputs[a].strip()}" for a in ANALYSTS
            )

        outputs["analysis"] = render_analysis()
        await _emit(
            engagement_id,
            "phase_completed",
            {"phase": "analysis", "agent": "5 specialist analysts", "output": render_analysis()},
        )

        # --- Engagement Manager reconciliation + governance (ADR-006) --------
        # Context budget: Groq 6 k TPM. Reconcile receives ONLY analyst outputs
        # (not the full accumulated phase history) to keep input ≤ 4 000 tokens.
        analysis_detail = _section("Analyst findings (supporting detail)", render_analysis())
        # Minimal reconcile context: case + issue tree + analyst outputs.
        reconcile_context = (
            case
            + _section("Issue tree", outputs["issue_tree"])
            + analysis_detail
        )

        canonical = await phase(
            "reconcile",
            "engagement-manager",
            reconcile_context
            + "\n\nReconcile the five analyst blocks above into the canonical "
            "reconciliation. Resolve every assumption-ID collision and every "
            "figure two analysts defined differently into ONE authoritative value.",
            system_override=ENGAGEMENT_MANAGER_SYSTEM,
            max_tokens=3500,
        )

        review = ""
        review_verdict = "needs_rework"
        for attempt in range(config.MAX_REWORK + 1):
            # Review context: case + issue tree + canonical + analyst notes.
            # The analyst notes get a "NOT reviewable" framing: they predate the
            # canonical ledger, so they cannot cite A-IDs and their figures may
            # be superseded — reviewing them for traceability/calibration would
            # fail every engagement on sequencing grounds, not substance.
            governance_context = (
                case
                + _section("Issue tree", outputs["issue_tree"])
                + _section("CANONICAL RECONCILIATION — single source of truth", canonical)
                + _section(
                    "Analyst working notes — context only, NOT reviewable",
                    "These notes were written BEFORE the canonical reconciliation "
                    "existed: analysts cannot cite canonical A-IDs that had not yet "
                    "been minted, and individual figures may be superseded by the "
                    "reconciliation. Do not raise traceability, calibration, or "
                    "ID-hygiene issues against this section.\n\n" + render_analysis(),
                )
            )
            review = await phase(
                "review",
                "reviewer",
                governance_context
                + "\n\nA CANONICAL RECONCILIATION has been provided above; treat it as "
                "the single source of truth and run all five checks (MECE, evidence "
                "traceability, consistency, calibration, gap closure) AGAINST it. "
                "Review scope — this is a single-pass pipeline, not the full "
                "state-machine harness: (1) the issue tree is a list of questions; "
                "its status/answer/evidence_refs fields are never updated after "
                "generation, so judge coverage by the 'Issue tree closure' table in "
                "the canonical reconciliation, never by the tree's own bookkeeping "
                "fields; (2) a placeholder or stale assumption ID inside raw analyst "
                "text is non-blocking when the canonical ledger resolves that figure — "
                "the reconciliation supersedes analyst detail; (3) apply the evidence-"
                "traceability and confidence-calibration checks ONLY to the canonical "
                "reconciliation tables — the analyst working notes predate the ledger "
                "and are exempt; (4) numbers stated in the case prompt are client "
                "facts — arithmetic performed directly on client facts needs no "
                "assumption reference; (5) fail ONLY for substantive defects: a "
                "load-bearing question with no answer in the closure table, a "
                "contradiction the reconciliation failed to resolve, a decision-"
                "critical figure with no quantification, or a canonical-ledger row "
                "whose confidence is unjustified. Verdict: approved / needs_rework.",
                max_tokens=2000,
            )
            review_verdict = _reviewer_verdict(review)
            await _emit(
                engagement_id,
                "review_verdict",
                {"verdict": review_verdict, "attempt": attempt + 1},
            )
            if review_verdict == "approved" or attempt == config.MAX_REWORK:
                break

            await _emit(
                engagement_id,
                "rework_started",
                {"agents": ["engagement-manager"], "attempt": attempt + 1},
            )
            canonical = await phase(
                "reconcile",
                "engagement-manager",
                reconcile_context
                + _section("Your previous canonical reconciliation", canonical)
                + _section("Reviewer's required fixes — resolve every one", review)
                + "\n\nProduce a corrected canonical reconciliation that fixes every "
                "issue the reviewer raised.",
                system_override=ENGAGEMENT_MANAGER_SYSTEM,
                max_tokens=6000,
            )
            await _emit(engagement_id, "rework_completed", {"attempt": attempt + 1})

        outputs["analysis"] = render_analysis()
        # Challenge and report: receive ONLY canonical + analyst outputs
        # (not the full prior-phase history) to keep input ≤ 3 500 tokens.
        final_context = (
            case
            + _section("Issue tree", outputs["issue_tree"])
            + _section("CANONICAL RECONCILIATION — single source of truth", canonical)
            + analysis_detail
        )

        challenge = await phase(
            "challenge",
            "challenger",
            final_context
            + _section("Reviewer notes", review)
            + f"\n\nReviewer verdict: {review_verdict}. Run your challenge NOW "
            "regardless of that verdict — this is a single-pass pipeline with no "
            "later opportunity, so the precondition that the reviewer must first "
            "approve does not apply here. Attack the load-bearing assumptions and "
            "build the strongest counter-case. Judge ONLY the substance of the "
            "recommendation — process or bookkeeping complaints belong to the "
            "reviewer, not you. End with exactly one line: `VERDICT: stands` or "
            "`VERDICT: stands_with_caveats` or `VERDICT: needs_rework`.",
            max_tokens=2000,
        )
        challenge_verdict = _challenger_verdict(challenge)
        await _emit(engagement_id, "challenge_verdict", {"verdict": challenge_verdict})

        review_ready = review_verdict == "approved" and challenge_verdict in (
            "stands",
            "stands_with_caveats",
        )

        report = await phase(
            "reporting",
            "report-writer",
            final_context
            + _section("Reviewer notes", review)
            + _section("Challenger notes", challenge)
            + f"\n\nGovernance state: reviewer={review_verdict}, challenger={challenge_verdict}. "
            + (
                "Both gates cleared — write the final executive-ready client report."
                if review_ready
                else "The gates did not fully clear after rework — write an honest interim "
                "status report that states plainly it is not a final recommendation and "
                "lists exactly what must be reconciled next."
            )
            + "\n\nUse the CANONICAL RECONCILIATION as the single source of truth for "
            "every number and every assumption ID — never cite a figure from the analyst "
            "detail that the canonical ledger supersedes.\n"
            "\nWrite it to MBB (McKinsey/Bain/BCG) partner standard:\n"
            f"- Start with an H1 title, then a meta line `**Prepared for:** the "
            f"board · **Date:** {_today()} · **Governance:** reviewer={review_verdict} · "
            f"challenger={challenge_verdict}`.\n"
            "- Lead with the answer (Pyramid Principle): the very first section is a "
            "`## Executive summary` whose first sentence is the single recommendation "
            "in one line, then the 2-3 reasons and the single biggest caveat.\n"
            "- Then: `## Situation`, `## Approach`, `## Analysis` (one subsection per "
            "issue-tree branch), `## Recommendation` (with numbered, sequenced next "
            "steps and 'alternatives rejected, and why'), `## Risks & what would change "
            "the answer`, and `## Appendix: assumptions log` (a markdown table with "
            "columns ID | Confidence | Assumption | Breakeven).\n"
            "- Use markdown tables for every option comparison and every set of "
            "figures; keep prose tight and decision-oriented (MECE, no hedging beyond "
            "the labeled assumptions).\n"
            "- Preserve every `[ASSUMPTION]` label verbatim and incorporate every "
            "challenger caveat. Never upgrade an assumption to a fact.\n"
            "- The recommendation must WIN THE NUMBERS: per the 'Options value "
            "comparison', if another option has higher risk-adjusted value, either "
            "recommend that option or quantify the factor (option value, risk "
            "asymmetry, strategic control) that closes the gap — in euros, in the "
            "executive summary. Never publish a report whose own counter-case is "
            "numerically dominant and unanswered.\n"
            "- Number hygiene: write money as €310.8M / €2,680M / €3.4B — commas "
            "for thousands, never periods (never `€2.680M` meaning €2,680M); use "
            "one consistent rounding per figure across the whole document.\n"
            f"- Every milestone, monitoring trigger, and due date must be AFTER "
            f"{_today()}; never reference a past quarter as a future checkpoint.\n"
            "- ID hygiene: cite ONLY canonical ledger IDs (A1, A2, …) everywhere — "
            "body sections included. Never copy an analyst-local ID (AL-n, A-001) "
            "into the report; if a source note used one, translate it to the "
            "canonical ID before citing. The appendix and the body must use one "
            "identical ID scheme.\n"
            "- Sanity-check the value logic in the executive summary: if the "
            "recommendation is to accept an offer, the offer must be shown ≥ the "
            "independent value of the alternative (or the gap explicitly priced); "
            "never state that an offer is below intrinsic value and recommend "
            "accepting it without pricing why.",
            max_tokens=config.REPORT_MAX_TOKENS,
        )

        db.set_engagement_status(engagement_id, "completed", report_md=report)
        db.set_governance(
            engagement_id,
            review_verdict=review_verdict,
            challenge_verdict=challenge_verdict,
            review_ready=review_ready,
        )

        # Learning loop: after EVERY engagement, distil durable process lessons
        # from what the reviewer and challenger caught — approved runs still
        # surface caveats worth guarding against next time. One cheap call;
        # never fails the engagement.
        try:
            focus = (
                "The gates did NOT clear — extract what went wrong in the method."
                if not review_ready
                else "The gates cleared — extract what the reviewer/challenger still "
                "flagged (caveats, near-misses) so the next engagement avoids "
                "even those."
            )
            reflection = await call(
                "reflector",
                REFLECTION_SYSTEM,
                _section("Reviewer notes", review)
                + _section("Challenger notes", challenge)
                + f"\n\n{focus}\nExtract the durable process lessons (method only, "
                "no case facts). Output `LESSON: ...` lines, or NONE.",
                api_key=api_key,
            )
            for lesson in _parse_lessons(reflection):
                if db.add_lesson(lesson, engagement_id):
                    await _emit(engagement_id, "lesson_learned", {"lesson": lesson})
        except Exception:  # noqa: BLE001 — reflection must never break a run
            pass

        await _emit(
            engagement_id,
            "engagement_completed",
            {
                "report": report,
                "review_ready": review_ready,
                "review_verdict": review_verdict,
                "challenge_verdict": challenge_verdict,
            },
        )

    except Exception as exc:  # noqa: BLE001 — surface any failure to the client
        message = friendly_error(exc)
        db.set_engagement_status(engagement_id, "failed", error=message)
        await _emit(engagement_id, "engagement_failed", {"error": message})
