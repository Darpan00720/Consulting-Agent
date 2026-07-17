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
import logging
import random
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any

from app import config, db
from app import telemetry_bridge as telemetry
from app.events import bus
from app.pipeline import (
    evidence_normalizer,
    evidence_schema,
    evidence_store,
    ledger_builder,
    prompts,
    quantcheck,
    sensitivity_analysis,
)
from app.pipeline.claude import call_agent, friendly_error
from app.pipeline.providers import AllProvidersRateLimitedError

log = logging.getLogger(__name__)

CallAgent = Callable[..., Awaitable[str]]


def _completed_phase_outputs(engagement_id: str) -> dict[str, str]:
    """Reconstruct each completed phase's output from persisted events.

    ``phase_completed`` events already carry the phase output, so a resumed
    run can skip finished phases instead of re-calling the model — the
    checkpoint that makes auto-resume-after-rate-limit lose no work.
    """
    out: dict[str, str] = {}
    for event in db.list_events(engagement_id):
        if event["type"] == "phase_completed":
            payload = event["payload"]
            if "output" in payload:
                out[payload["phase"]] = payload["output"]
    return out


def _completed_analyst_outputs(engagement_id: str) -> dict[str, str]:
    """Reconstruct individual analyst outputs from persisted events.

    The five analysts run sequentially with a 65 s throttle between them — the
    slowest stretch and the likeliest place to exhaust a rate limit. Caching
    each one means a resume re-runs only the analysts that hadn't finished.
    """
    out: dict[str, str] = {}
    for event in db.list_events(engagement_id):
        if event["type"] == "analyst_completed":
            payload = event["payload"]
            if payload.get("output") is not None:
                out[payload["agent"]] = payload["output"]
    return out


def _reviewer_verdict(text: str) -> str:
    """Extract 'approved' | 'needs_rework' from the reviewer's markdown.

    Prefers a verdict-context match; falls back to a bare token; **fails
    closed** — an unparseable reviewer response defaults to 'needs_rework', not
    'approved'. A gate whose verdict cannot be read has NOT been shown to pass,
    and this platform's whole premise is refusing to ship unverified analysis
    (ADR-006). This never hangs: the rework loop is bounded by MAX_REWORK, after
    which the report-writer produces an honest interim memo (review_ready=False)
    rather than a report falsely claiming the gate cleared.
    """
    low = text.lower()
    m = re.search(r"verdict[^\n]{0,40}?(needs[_ ]rework|approved)", low)
    if m:
        return "needs_rework" if "rework" in m.group(1) else "approved"
    if re.search(r"\bapproved\b", low) and not re.search(r"needs[_ ]rework", low):
        return "approved"
    return "needs_rework"


def _challenger_verdict(text: str) -> str:
    """Extract 'stands' | 'stands_with_caveats' | 'needs_rework' (order matters
    since 'stands_with_caveats' contains 'stands').

    **Fails closed**: an unparseable challenger response defaults to
    'needs_rework', which makes review_ready False and yields an honest interim
    memo. Same reasoning as the reviewer — an unreadable stress-test verdict is
    not evidence the recommendation survived attack.
    """
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
        return "needs_rework"
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

# ADR-010 Phase 2: each analyst emits evidence atoms scoped to its own domain
# category, so the Evidence Validator/Store can attribute and query atoms by
# category without guessing from the agent name at query time.
_EVIDENCE_CATEGORY = {
    "financial-analyst": "financial",
    "market-analyst": "market",
    "operations-analyst": "operational",
    "strategy-analyst": "strategic",
    "risk-analyst": "risk",
}

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

## Client question closure
ONLY when the context contains a "QUESTIONS THE CLIENT ASKED" list. One row per
question, in the client's order — this is what the engagement is graded on, and
it outranks the issue tree (the tree is ours; the questions are theirs).
Columns: Q# | Question (abbreviated) | Answer (direct, quantified, self-
contained) | Basis (canonical IDs).
Rules: answer EVERY question. Arithmetic questions must show the computation and
the result — recompute it yourself from the client's stated numbers rather than
trusting an analyst's figure, and if your result disagrees with theirs, yours
wins and you say so in Corrections applied. A judgement question ("would you
exit Germany?") needs a committed answer, not a restatement. If a question truly
cannot be answered from the material, mark it OPEN and say what is missing —
never silently drop it.

## Corrections applied
A bullet list of every collision or contradiction you resolved (ID reused,
number in dispute, citation to a stale value) and how you resolved it.

## Evidence atoms
The LAST thing in your output: a fenced code block opened with ```atoms
containing ONE JSON array of EVIDENCE ATOMS (ADR-010). You do NOT write the
ledger, mint ids, wire formula references, or compute any derived value —
deterministic code does all of that from your atoms and a verifier then checks
it. Your job is only to supply the evidence: the facts, the assumptions with
their bands, and the SHAPE of each calculation. Every number cited anywhere
above (reconciled key figures, options comparison, question closures) must trace
to an atom here.

An atom references OTHER atoms by their ``key`` (a slug you choose), never by an
id — ids do not exist yet. Three kinds:

  {"key":"revenue","kind":"fact","label":"Annual revenue","value":324,
   "unit":"EUR_M","scope":"annual","source":"client_fact: '€324M revenue'"}

  {"key":"delivery_share","kind":"assumption","label":"Delivery share of sales",
   "value":0.20,"unit":"RATIO","scope":"annual","source":"analyst_estimate",
   "low":0.10,"high":0.25}

  {"key":"drain","kind":"derived","label":"Delivery commission drain",
   "unit":"EUR_M","scope":"annual",
   "expr":"revenue * delivery_share * commission"}

Rules (the builder + verifier enforce these):
- A ``fact`` is client-stated: give ``value`` and a ``source`` quoting the case.
- An ``assumption`` needs ``value``, a ``source`` naming where the number would
  come from (POS, CRM, financials, contract, benchmark), and a plausibility band
  ``low``/``high`` that contains ``value``.
- A ``derived`` atom gives ONLY an ``expr`` over other atom keys, using
  + - * / ** and parentheses. DO NOT give it a ``value`` — the code computes it
  exactly, so you cannot get the arithmetic wrong (and must not try).
- Rates are RATIO (0.05 = 5%), never PCT. Never mix units or time scopes in one
  ``expr`` (annual + cumulative is a defect).
- For any profitability / cost-change case, include a BRIDGE: derived atoms for
  each component of the period-over-period change — volume/revenue scaling
  (base-period cost ratio × the revenue change), price/inflation, mix, one-offs
  — plus a total derived atom with ``"bridge": true`` whose ``expr`` is the pure
  +/- sum of those component keys. The unexplained residual is itself a derived
  atom.
- Where a derived figure has an independent factual counterpart (e.g. market
  share implied by SOM vs the company's actual revenue over the same market
  size), set ``"anchor":"<key>"`` on it so the verifier cross-checks them.

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
            lesson = line[len("LESSON:") :].strip()
            if lesson and lesson.upper() != "NONE":
                out.append(lesson[:400])
    return out


_engagement_semaphore: asyncio.Semaphore | None = None


def _engagement_slot() -> asyncio.Semaphore:
    """Server-wide cap on concurrently-running engagements (lazy singleton).

    Created on first use so it binds to the running event loop. Bounds load on
    the single SQLite writer and the shared provider quota; work beyond the cap
    waits its turn instead of piling on unbounded.
    """
    global _engagement_semaphore
    if _engagement_semaphore is None:
        _engagement_semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_ENGAGEMENTS)
    return _engagement_semaphore


async def run_engagement(
    engagement_id: str,
    case_prompt: str,
    *,
    call: CallAgent = call_agent,
    api_key: str | None = None,
    model: str | None = None,
    images: list[str] | None = None,
    resume_count: int = 0,
) -> None:
    """Run one full engagement under the concurrency cap.

    Thin wrapper over :func:`_run_engagement` that holds one engagement slot for
    the duration. A paused engagement releases its slot while it waits (the
    resume re-invokes this and re-acquires), so slow rate-limited runs don't
    block fresh ones.
    """
    async with _engagement_slot():
        await _run_engagement(
            engagement_id,
            case_prompt,
            call=call,
            api_key=api_key,
            model=model,
            images=images,
            resume_count=resume_count,
        )


async def _run_engagement(
    engagement_id: str,
    case_prompt: str,
    *,
    call: CallAgent = call_agent,
    api_key: str | None = None,
    model: str | None = None,
    images: list[str] | None = None,
    resume_count: int = 0,
) -> None:
    """Run one full engagement. Persists status/report and emits events.

    ``api_key`` is the user's own key (BYOK); ``None`` uses server credentials.
    ``model`` overrides the default Claude model for every agent call.
    ``images`` are pasted charts/graphs passed to vision-capable providers.

    Resumable: if every provider is rate-limited mid-run the engagement is
    paused and re-invoked later with the same arguments. Completed phases and
    analysts are reconstructed from persisted events and skipped, so a resume
    picks up exactly where it left off. ``resume_count`` bounds the retries.
    """
    # Checkpoints reconstructed from persisted events (empty on a fresh run).
    done: dict[str, str] = _completed_phase_outputs(engagement_id)
    analyst_cache: dict[str, str] = _completed_analyst_outputs(engagement_id)
    resuming = bool(done or analyst_cache)

    db.set_engagement_status(engagement_id, "running")
    if resuming:
        await _emit(
            engagement_id,
            "engagement_resumed",
            {"completed_phases": sorted(done), "attempt": resume_count},
        )
    else:
        await _emit(
            engagement_id, "engagement_started", {"phases": [p for p, _ in PHASES]}
        )
    outputs: dict[str, str] = {}

    async def phase(
        name: str,
        agent: str,
        user_message: str,
        *,
        system_override: str | None = None,
        checkpoint: bool = True,
        images: list[str] | None = None,
        signals: Callable[[str], dict[str, Any]] | None = None,
        **kw: Any,
    ) -> str:
        # Resume: a checkpointed phase already completed in an earlier pass —
        # return its stored output without re-calling the model.
        if checkpoint and name in done:
            return done[name]
        await _emit(engagement_id, "phase_started", {"phase": name, "agent": agent})
        started = time.monotonic()
        system = system_override or prompts.agent_system_prompt(agent)
        # Operational span (separate from the domain event above): records real
        # wall time and FAILED on exception, for operators. Never load-bearing.
        # `signals` derives metadata from the result (e.g. a governance verdict)
        # and rides this span's single terminal event — emitting a second event
        # instead would double-count in the core's analytics.
        with telemetry.span(engagement_id, agent, name) as handle:
            result = await call(
                agent,
                system,
                user_message,
                api_key=api_key,
                model=model,
                images=images,
                **kw,
            )
            if signals is not None:
                telemetry.attach(handle, **signals(result))
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
        done[name] = result
        return result

    try:
        case = f"# Case prompt\n\n{case_prompt.strip()}"
        # When the client hands us a structured question list rather than a
        # narrative brief, the deliverable is ANSWERS — not a synthesized memo
        # about a decomposition we invented. Extracted deterministically from
        # the client's own text so the reviewer grades coverage against what was
        # actually asked, not against our self-generated issue tree.
        asked = prompts.question_checklist(case_prompt)
        asked_section = (
            _section(
                "QUESTIONS THE CLIENT ASKED — every one requires an explicit answer",
                asked + "\n\nThese are the client's own words. A fluent report that "
                "answers none of them is a wrong answer.",
            )
            if asked
            else ""
        )
        # The learning loop: standing lessons from past engagements, injected as
        # guardrails so recurring errors are avoided this time.
        lessons = _standing_lessons()

        outputs["classify"] = await phase(
            "classify",
            "case-classifier",
            f"{case}\n\nProduce the structured intake brief."
            + (
                "\n\nThe user attached image(s) (charts, graphs, screenshots) "
                "below — read them as part of the brief and incorporate what "
                "they show."
                if images
                else ""
            ),
            images=images,
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
            "confidence, breakeven) rather than escalating to a human. For every "
            "assumption also state (1) its SOURCE — where the number would come "
            "from in a real engagement: POS, CRM, financial statements, supplier "
            "contract, or a named industry benchmark — and (2) a plausibility "
            "band low–high the working value sits inside. An assumption whose "
            "band you cannot defend against a benchmark is an OPEN gap; say so "
            "explicitly instead of adopting it.",
            images=images,
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
            + asked_section
            + _section("Intake brief", outputs["classify"])
            + _section("Framework selection", outputs["framing"])
            + knowledge_section
            + lessons
            + "\n\nBuild the MECE issue tree with owned, testable leaves.\n\n"
            + (
                "The client asked explicit questions (listed above). The tree "
                "MUST cover every one — a leaf that answers each. A tree that is "
                "elegant but leaves the client's questions unanswered is a MECE "
                "failure, because the client's questions ARE the problem space.\n\n"
                if asked
                else ""
            )
            + "If this is an acquisition / M&A / market-entry case, the tree MUST be "
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
            "6. Strategic ALTERNATIVES — other targets, partner vs build vs"
            " acquire, and not pursuing this move at all.\n"
            "7. Integration and execution risk.\n"
            "Assign each branch to the most appropriate owner; the market-analyst owns "
            "commercial-capability and go-to-market branches, not just market sizing.",
            images=images,
            max_tokens=3000,
        )

        # --- analysis: five specialists in SEQUENTIAL order -------------------
        # Groq free tier: 6 000 TPM. Each analyst call is ~3 000 tokens total
        # (1 000 input + 2 000 max output). The throttle in claude.py enforces
        # 65 s between calls, giving the bucket 6 500 token refill headroom.
        # Analysts run one-at-a-time (no semaphore needed) using MINIMAL context:
        # only case + key assumptions + issue tree — not all 5 prior outputs.
        analysis_done = "analysis" in done
        if not analysis_done:
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

        async def run_analyst(agent: str) -> str:
            # Resume: a finished analyst is served from the checkpoint cache,
            # so a rate-limit pause never re-runs work that already landed.
            if agent in analyst_cache:
                return analyst_cache[agent]
            await _emit(engagement_id, "analyst_started", {"agent": agent})
            started = time.monotonic()
            # The 5 analysts are the longest stretch of an engagement and the
            # likeliest place to exhaust a rate limit — per-analyst spans are
            # what let an operator see WHICH one is slow or failing.
            with telemetry.span(engagement_id, agent, "analysis"):
                bridge_rule = (
                    "\n\nIf the case involves a profit or cost change over time, "
                    "build a PERIOD-OVER-PERIOD BRIDGE: decompose the change into "
                    "volume/revenue scaling (costs grow with revenue at the "
                    "base-period cost ratio — never treat natural variable-cost "
                    "growth as unexplained), price/inflation, mix, and one-offs. "
                    "The residual is what remains AFTER the scaling term — "
                    "computed, never guessed. Apply each YoY rate over the full "
                    "period in question, not a single year."
                    if agent == "financial-analyst"
                    else ""
                )
                category = _EVIDENCE_CATEGORY[agent]
                evidence_rule = (
                    "\n\nEnd your response with a ```evidence fenced JSON array — "
                    "ADR-010 Phase 2: this is now your PRIMARY, machine-read output; "
                    "the platform builds the ledger from atoms, never from your "
                    "prose. Every atom needs 'category':\""
                    + category
                    + '". Three kinds:\n'
                    '  {"atom_id":"revenue","category":"'
                    + category
                    + '","type":"fact","title":"Annual revenue",'
                    '"value":324,"unit":"EUR_M","scope":"annual",'
                    '"source_type":"client_fact"}\n'
                    '  {"atom_id":"delivery_share","category":"'
                    + category
                    + '","type":"assumption","title":"Delivery share of sales",'
                    '"value":0.20,"unit":"RATIO","scope":"annual",'
                    '"source_type":"analyst_estimate","low":0.10,"high":0.25}\n'
                    '  {"atom_id":"drain","category":"'
                    + category
                    + '","type":"derived","title":"Delivery commission drain",'
                    '"unit":"EUR_M","scope":"annual",'
                    '"formula":"revenue * delivery_share * commission_rate"}\n'
                    "'fact'/'assumption' need value+source_type (client_fact, "
                    "benchmark, analyst_estimate, or external_research); an "
                    "'assumption' also needs low/high. A 'derived' atom gives ONLY "
                    "'formula' over other atoms' atom_id — never a value; it is "
                    "computed for you. Rates are RATIO (0.20), never PCT/'%'. "
                    "atom_id is a slug (letters/digits/underscore)."
                )
                result = await call(
                    agent,
                    prompts.agent_system_prompt(agent),
                    analyst_base_context
                    + f"\n\nAnswer only the issue-tree branches owned by the {agent}. "
                    "Lead with ONE short paragraph (under 120 words) naming your "
                    "headline finding — the evidence block below is what carries "
                    "the actual analysis; do not repeat figures in prose that "
                    "belong in an atom." + bridge_rule + evidence_rule,
                    api_key=api_key,
                    model=model,
                    images=images,
                    max_tokens=2000,
                )
            await _emit(
                engagement_id,
                "analyst_completed",
                {
                    "agent": agent,
                    "duration_ms": round((time.monotonic() - started) * 1000),
                    "output": result,
                },
            )
            analyst_cache[agent] = result
            return result

        # Run analysts sequentially to stay within Groq 6 k TPM.
        analyst_outputs: dict[str, str] = {}
        for analyst_name in ANALYSTS:
            analyst_outputs[analyst_name] = await run_analyst(analyst_name)

        def render_analysis() -> str:
            return "\n\n".join(
                f"## {a}\n\n{analyst_outputs[a].strip()}" for a in ANALYSTS
            )

        outputs["analysis"] = render_analysis()
        if not analysis_done:
            done["analysis"] = outputs["analysis"]
            await _emit(
                engagement_id,
                "phase_completed",
                {
                    "phase": "analysis",
                    "agent": "5 specialist analysts",
                    "output": render_analysis(),
                },
            )

        # --- Evidence Validator -> Normalizer -> Store (ADR-010 Phase 2) -----
        # Each analyst emitted its OWN evidence atoms (category-scoped). A
        # malformed block is REJECTED here (Task 5) rather than silently
        # passed downstream — but rejection only drops that analyst's atoms;
        # its prose still reaches the EM below, so one analyst's bad JSON
        # never fails the engagement (Task 7 backward compatibility).
        evidence_errors: dict[str, tuple[str, ...]] = {}
        validated_atoms: list[evidence_schema.EvidenceAtom] = []
        for agent in ANALYSTS:
            parsed = evidence_schema.parse_evidence_block(
                analyst_outputs[agent], created_by=agent
            )
            if parsed.errors:
                evidence_errors[agent] = parsed.errors
                continue
            validated_atoms.extend(parsed.atoms)

        normalized = evidence_normalizer.normalize(validated_atoms)
        evidence_store_obj = evidence_store.build_store(list(normalized.atoms))
        await _emit(
            engagement_id,
            "evidence_validated",
            {
                "atoms": len(evidence_store_obj),
                "rejected_analysts": sorted(evidence_errors),
                "validator_errors": [
                    msg for errs in evidence_errors.values() for msg in errs
                ],
                "normalizer_warnings": list(normalized.warnings),
                "conflicts": [a.atom_id for a in evidence_store_obj.conflicts()],
            },
        )

        # --- Engagement Manager reconciliation + governance (ADR-006) --------
        # Context budget: Groq 6 k TPM. Reconcile receives ONLY analyst outputs
        # (not the full accumulated phase history) to keep input ≤ 4 000 tokens.
        analysis_detail = _section(
            "Analyst findings (supporting detail)", render_analysis()
        )
        # The Store's pre-validated, pre-normalized atoms — when any analyst
        # produced valid evidence — so the EM reconciles a STRUCTURED starting
        # point instead of re-deriving atoms from prose alone. Empty when no
        # analyst produced a parseable evidence block, in which case the EM
        # falls back to exactly Phase 1's tested from-prose behavior.
        evidence_section = (
            _section(
                "PRE-VALIDATED EVIDENCE (already extracted, unit/currency/"
                "percentage-normalized, and deduplicated from the analysts' "
                "structured evidence — ADR-010 Phase 2)",
                "```atoms\n" + evidence_store_obj.to_atoms_block() + "\n```\n"
                "This is a starting point, not a finished ledger: a key "
                "containing '__' (e.g. `revenue__financial-analyst`) is a "
                "CONFLICT the normalizer could not resolve — two analysts "
                "defined it differently. Pick ONE authoritative value per "
                "conflict (prefer the more conservative / better-sourced), "
                "fold it back under the single un-suffixed key, and carry "
                "every other atom through unchanged into your own ```atoms "
                "block below.",
            )
            if len(evidence_store_obj)
            else ""
        )
        # Minimal reconcile context: case + issue tree + analyst outputs.
        reconcile_context = (
            case
            + asked_section
            + _section("Issue tree", outputs["issue_tree"])
            + evidence_section
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
            checkpoint=False,  # governance re-runs on resume (cheap; analysts cached)
            max_tokens=3500,
        )

        # --- Quant Gate (ADR-009): deterministic math verification -----------
        # The verifier is code, not an LLM: it re-evaluates every ledger
        # formula in exact decimal arithmetic. Failures produce an exact,
        # machine-generated defect list that goes straight back to the
        # Engagement Manager — cheaper and stricter than an LLM review, and it
        # runs BEFORE the reviewer so LLM review budget is spent on judgment,
        # never on arithmetic. Fix budget is shared across the whole run so a
        # reviewer-driven rework that breaks the ledger can still be repaired.
        quant_fixes_left = config.MAX_REWORK + 1

        def _build_and_verify(
            canonical: str,
        ) -> tuple[str, quantcheck.QuantReport]:
            # ADR-010 P1: assemble the ledger from the EM's evidence ATOMS
            # deterministically (code mints ids, wires formulas, and computes
            # every derived value), THEN run the verifier. A builder failure
            # (malformed atoms) is surfaced as a QuantReport so it flows through
            # the exact same rework loop, emit, and telemetry as a gate defect.
            built = ledger_builder.build_from_markdown(canonical)
            if built.errors:
                defects = tuple(
                    quantcheck.QuantDefect("atoms", (), msg) for msg in built.errors
                )
                return canonical, quantcheck.QuantReport(False, defects, None)
            return built.markdown, quantcheck.verify_ledger(built.markdown)

        async def quant_verified(
            canonical: str,
        ) -> tuple[str, quantcheck.QuantReport]:
            nonlocal quant_fixes_left
            canonical, verdict = _build_and_verify(canonical)
            while not verdict.passed and quant_fixes_left > 0:
                quant_fixes_left -= 1
                await _emit(
                    engagement_id,
                    "quant_gate",
                    {
                        "passed": False,
                        "fixing": True,
                        "defects": [d.message for d in verdict.defects],
                    },
                )
                canonical = await phase(
                    "reconcile",
                    "engagement-manager",
                    reconcile_context
                    + _section("Your previous canonical reconciliation", canonical)
                    + _section(
                        "QUANT GATE DEFECTS — deterministic output. These are "
                        "exact; every one must be fixed",
                        quantcheck.format_defects(verdict),
                    )
                    + "\n\nRe-issue the FULL canonical reconciliation with a "
                    "corrected ```atoms block. Fix exactly what the defects "
                    "name — correct the atom's value, band, unit, source, or "
                    "expr. Remember: you supply evidence atoms only; the code "
                    "computes derived values, so never put a value on a derived "
                    "atom. Conclusions stay unchanged unless a corrected number "
                    "genuinely invalidates them, in which case say so in "
                    "Corrections applied.",
                    system_override=ENGAGEMENT_MANAGER_SYSTEM,
                    checkpoint=False,
                    max_tokens=6000,
                )
                canonical, verdict = _build_and_verify(canonical)
            await _emit(
                engagement_id,
                "quant_gate",
                {
                    "passed": verdict.passed,
                    "fixing": False,
                    "defects": [d.message for d in verdict.defects],
                },
            )
            # A (near-zero-duration) span, not a bare emit: FINISHED events
            # must carry durations, and validation_status rides the terminal
            # event the same way the reviewer's verdict does. reconcile maps
            # to ORCHESTRATION, so quality analytics for REVIEW stay clean.
            with telemetry.span(engagement_id, "quant-gate", "reconcile") as handle:
                telemetry.attach(
                    handle,
                    validation_status="passed" if verdict.passed else "blocked",
                    quant_defects=len(verdict.defects),
                )
            return canonical, verdict

        canonical, quant = await quant_verified(canonical)

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
                + asked_section
                + _section("Issue tree", outputs["issue_tree"])
                + _section(
                    "CANONICAL RECONCILIATION — single source of truth", canonical
                )
                + _section(
                    "Deterministic quant gate (ADR-009)",
                    (
                        "PASSED — a deterministic verifier has re-evaluated every "
                        "formula in the quant ledger in exact decimal arithmetic; "
                        "units, bounds, anchors, and bridge closure all check out. "
                        "Do NOT spend review effort re-doing arithmetic, and never "
                        "fail a figure because your own mental math differs — the "
                        "machine's evaluation is authoritative."
                        if quant.passed
                        else "FAILED — the quant ledger still has machine-verified "
                        "defects after the fix budget was exhausted:\n"
                        + quantcheck.format_defects(quant)
                        + "\nThe engagement cannot be review-ready; still review "
                        "the substance so the rework is complete."
                    ),
                )
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
                "whose confidence is unjustified; (6) arithmetic is MACHINE-"
                "VERIFIED upstream (see the quant-gate section) — your job is "
                "judgment: MECE coverage, causality (is the named driver a cause "
                "or a correlate — what alternative explanation would produce the "
                "same numbers?), evidence quality, and calibration."
                + (
                    " (7) COVERAGE OF THE CLIENT'S QUESTIONS — this outranks every "
                    "other check. The client asked explicit questions (listed above "
                    "under 'QUESTIONS THE CLIENT ASKED'). Walk that list and confirm "
                    "each has an actual answer in the canonical reconciliation. Any "
                    "unanswered question is a substantive defect — return "
                    "needs_rework and name the specific Q-numbers that are missing. "
                    "Judging coverage only by the issue tree is grading our own "
                    "homework: the tree is something we generated, the questions are "
                    "what the client actually wants. A well-structured memo that "
                    "answers a question the client did not ask is a failed "
                    "engagement, not an approved one."
                    if asked
                    else ""
                )
                + " Verdict: approved / needs_rework.",
                checkpoint=False,
                max_tokens=2000,
                # Governance outcome rides this span's terminal event: the
                # core's quality_analytics reads metadata["verdict"] off
                # terminal REVIEW events to compute reviewer_pass_rate.
                signals=lambda text: {
                    "verdict": _reviewer_verdict(text),
                    "validation_status": (
                        "passed" if _reviewer_verdict(text) == "approved" else "blocked"
                    ),
                },
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
                "issue the reviewer raised. Keep the ```atoms block in sync: every "
                "figure you change must change in its atom too (value for a fact/"
                "assumption, expr for a derived one).",
                system_override=ENGAGEMENT_MANAGER_SYSTEM,
                checkpoint=False,
                max_tokens=6000,
            )
            # A reviewer-driven rework may have altered figures — the quant
            # gate re-verifies (and deterministically repairs, within budget)
            # so a rework can never trade a judgment fix for broken math.
            canonical, quant = await quant_verified(canonical)
            await _emit(engagement_id, "rework_completed", {"attempt": attempt + 1})

        outputs["analysis"] = render_analysis()
        # Challenge and report: receive ONLY canonical + analyst outputs
        # (not the full prior-phase history) to keep input ≤ 3 500 tokens.
        final_context = (
            case
            + asked_section
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
            "reviewer, not you. The arithmetic itself is machine-verified "
            "(quant gate), so attack the MODEL, not the sums — run this "
            "KILLER-QUESTION checklist and answer each in one or two lines:\n"
            "(a) BASIS — is each headline figure run-rate or cumulative, and "
            "does the recommendation still clear its hurdle on the other "
            "reading?\n"
            "(b) BREAKEVEN — which single assumption, moved to the edge of its "
            "stated low–high band, flips the recommendation? Say which and at "
            "what value.\n"
            "(c) MEAN REVERSION — if the largest cost or growth driver reverts "
            "to its historical norm next year, does the recommendation survive?\n"
            "(d) CAUSALITY — for each named cause, state the strongest "
            "alternative explanation that produces the same numbers, and "
            "whether the evidence distinguishes them.\n"
            "(e) THE CEO TEST — name the two most obvious simpler moves (raise "
            "price, close the worst stores, cut HQ, exit the channel) and why "
            "the recommendation beats each, in euros.\n"
            "End with exactly one line: `VERDICT: stands` or "
            "`VERDICT: stands_with_caveats` or `VERDICT: needs_rework`.",
            checkpoint=False,
            max_tokens=2000,
            signals=lambda text: {
                "verdict": _challenger_verdict(text),
                "validation_status": (
                    "blocked"
                    if _challenger_verdict(text) == "needs_rework"
                    else "passed"
                ),
            },
        )
        challenge_verdict = _challenger_verdict(challenge)
        await _emit(engagement_id, "challenge_verdict", {"verdict": challenge_verdict})

        # The quant gate is a full governance gate: verified math is as
        # mandatory as reviewer approval — a report whose numbers the machine
        # could not verify is never presented as final.
        review_ready = (
            quant.passed
            and review_verdict == "approved"
            and challenge_verdict in ("stands", "stands_with_caveats")
        )

        # --- Sensitivity analysis (ADR-010 P3) --------------------------------
        # Pure function of an already-verified ledger — zero new LLM calls, so
        # this runs unconditionally whenever there IS a verified ledger to
        # analyze. "Which assumption would flip the recommendation" becomes a
        # computed ranking instead of the report-writer's own guess.
        sensitivity_section = ""
        if quant.passed and quant.entries:
            top_sensitivity = sensitivity_analysis.analyze_sensitivity(quant.entries)
            await _emit(
                engagement_id,
                "sensitivity_analyzed",
                {
                    "results": [
                        {
                            "assumption_id": r.assumption_id,
                            "swing": str(r.swing),
                            "affected": list(r.affected),
                        }
                        for r in top_sensitivity
                    ]
                },
            )
            if top_sensitivity:
                sensitivity_section = _section(
                    "COMPUTED SENSITIVITY RANKING (ADR-010 P3 — exact, not a " "guess)",
                    "Every assumption with a plausibility band was re-evaluated "
                    "at its low and high bound against the verified ledger; "
                    "ranked by the largest resulting swing in any dependent "
                    "figure. Use this — do not independently guess which "
                    "assumption matters most.\n"
                    + "\n".join(
                        f"- {r.assumption_id}: swinging between its stated "
                        f"low ({r.low_value}) and high ({r.high_value}) moves "
                        f"{', '.join(r.affected)} by up to {r.swing}."
                        for r in top_sensitivity[:5]
                    ),
                )

        report_budget = (
            config.REPORT_MAX_TOKENS
            + 220 * len(prompts.explicit_questions(case_prompt))
            if asked
            else config.REPORT_MAX_TOKENS
        )
        report = await phase(
            "reporting",
            "report-writer",
            final_context
            + _section("Reviewer notes", review)
            + _section("Challenger notes", challenge)
            + sensitivity_section
            + f"\n\nGovernance state: reviewer={review_verdict},"
            + f" challenger={challenge_verdict},"
            + f" quant-gate={'verified' if quant.passed else 'FAILED'}. "
            + (
                "All gates cleared — write the final executive-ready client report."
                if review_ready
                else "THE GATES DID NOT CLEAR. Write an INTERIM status memo, not a "
                "decision document. Rules you MUST follow because the numbers are "
                "not verified: (1) do NOT present a final recommendation — frame "
                "the strongest option as 'the leading candidate, PROVISIONAL "
                "pending reconciliation' and say what must be resolved before it "
                "can be acted on; (2) do NOT write a 'decision required by <date>' "
                "line or any language that invites the Board to act now; (3) the "
                "meta line's Governance field MUST read "
                f"'reviewer={review_verdict} · challenger={challenge_verdict} · "
                "quant-gate=FAILED — INTERIM' — never show an all-clear governance "
                "line when a gate failed."
            )
            + "\n\nUse the CANONICAL RECONCILIATION as the single source of truth"
            " for every number and every assumption ID — never cite a figure from"
            " the analyst detail that the canonical ledger supersedes.\n"
            + (
                "\nTHE CLIENT ASKED EXPLICIT QUESTIONS (listed above). They are the "
                "deliverable. Answer EVERY ONE, in their order, under a dedicated "
                "section — each answer labelled with its Q-number, direct and "
                "self-contained. Where a question is arithmetic, SHOW THE "
                "CALCULATION and state the result; do not gesture at it. Where a "
                "question asks for a judgement (would you exit / would you raise "
                "price / what would you do if it were your company), COMMIT to an "
                "answer and give the reason — 'it depends' is not an answer. You may "
                "still lead with an executive summary, but a memo that covers your "
                "own framing while leaving the client's questions unanswered is a "
                "failed deliverable, however well written.\n"
                if asked
                else ""
            )
            + "\nWrite it to MBB (McKinsey/Bain/BCG) partner standard:\n"
            f"- Start with an H1 title, then a meta line `**Prepared for:** the "
            f"board · **Date:** {_today()} · **Governance:**"
            f" reviewer={review_verdict} · "
            f"challenger={challenge_verdict} · "
            f"quant-gate={'verified' if quant.passed else 'FAILED — INTERIM'}`.\n"
            "- Lead with the answer (Pyramid Principle): the very first section is a "
            "`## Executive summary` whose first sentence is the single recommendation "
            "in one line, then the 2-3 reasons and the single biggest caveat.\n"
            "- Then: `## Situation`, `## Approach`, `## Analysis` (one subsection per "
            "issue-tree branch), `## Recommendation` (with numbered, sequenced next "
            "steps and 'alternatives rejected, and why'), `## Risks & what would"
            " change the answer`, "
            + (
                "`## Answers to your questions` — MANDATORY, non-negotiable, placed "
                "immediately after `## Recommendation`. One `### Q<n>.` subsection "
                "per client question, in the client's order, copied from the "
                "'Client question closure' table of the canonical reconciliation. "
                "Every question gets a direct answer; arithmetic questions show the "
                "computation AND the result; judgement questions commit to a "
                "position. This section is the deliverable — a report that omits it "
                "has failed the engagement no matter how good the rest is. "
                if asked
                else ""
            )
            + "and `## Appendix: assumptions log` (a markdown"
            " table with "
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
            "accepting it without pricing why.\n"
            "- QUANT DISCIPLINE (machine-enforced): every figure you write must "
            "be a quant-ledger value or a number stated in the client's case "
            "prompt. You may round a ledger value for prose, but NEVER re-derive, "
            "combine, or invent a number — a figure you want that is not in the "
            "ledger does not go in the report. A deterministic tie-out scans the "
            "finished report and flags every orphan number.",
            checkpoint=False,
            # A structured case must fit a full memo AND an answer per question.
            # At the base budget the model spends it all on the memo and silently
            # drops the answers — the failure this whole change exists to fix.
            max_tokens=report_budget,
        )

        # --- Report tie-out (ADR-009 §2.3): no orphan numbers -----------------
        # Run whenever there is a parsed ledger to check against, REGARDLESS of
        # review_ready — a report-writer prompted with "the gates did not fully
        # clear, write an honest interim memo" is a REQUEST, not a guarantee;
        # a live run (2026-07-16) showed a free-tier model ignore it and write
        # a fully-confident final-looking report despite quant.passed=False.
        # The banner below is the deterministic backstop for that non-
        # compliance — it does not depend on the model having obeyed anything.
        # Tie-out needs entries to check report numbers against; with no
        # parsed ledger at all there is nothing to compare, but the report
        # still gets the banner below via `unresolved`, seeded from
        # quant.defects (e.g. "no ```quant ledger block found").
        tie = (
            quantcheck.tie_out(report, quant.entries, case_prompt)
            if quant.entries is not None
            else quantcheck.QuantReport(True, (), None)
        )
        if quant.passed and not tie.passed:
            # Ledger was fine; only the report cited orphan numbers — worth
            # one rework, since the fix is narrow (swap the bad figures).
            await _emit(
                engagement_id,
                "quant_tie_out",
                {
                    "passed": False,
                    "fixing": True,
                    "defects": [d.message for d in tie.defects],
                },
            )
            report = await phase(
                "reporting",
                "report-writer",
                final_context
                + _section("Your previous report", report)
                + _section(
                    "ORPHAN NUMBERS — deterministic tie-out output. Every "
                    "one must be resolved",
                    quantcheck.format_defects(tie),
                )
                + "\n\nRe-issue the FULL report. Replace every orphan number "
                "with the correct quant-ledger value (rounded for prose is "
                "fine) or remove the claim — never invent a bridging figure. "
                "Change nothing else.",
                checkpoint=False,
                max_tokens=report_budget,
            )
            tie = quantcheck.tie_out(report, quant.entries, case_prompt)
        # Never re-run report-writer over broken LEDGER math (as opposed to an
        # orphan-number miss) — the EM already exhausted its fix budget; asking
        # report-writer to "fix" arithmetic it didn't produce just burns a
        # call. Report the defects verbatim instead of hiding them.
        unresolved = (list(quant.defects) if not quant.passed else []) + (
            [] if tie.passed else list(tie.defects)
        )
        if unresolved:
            review_ready = False
            # Cap the defect list so a ledger that failed on dozens of rows
            # doesn't bury the report under a wall of near-identical lines.
            shown = unresolved[:8]
            more = len(unresolved) - len(shown)
            defect_lines = "\n".join(f"> - {d.message}" for d in shown) + (
                f"\n> - …and {more} more deterministic defect(s)." if more else ""
            )
            # This banner is the guaranteed-correct governance signal: it does
            # NOT depend on the report-writer having obeyed the interim
            # instruction. It states the true governance line (quant gate
            # included, so it can't read all-clear like the model's own meta
            # line might) AND explicitly demotes every recommendation below to
            # provisional — closing the "banner says not-ready, body says
            # 'Decision required by …'" contradiction a real run exposed.
            report = (
                "> **⚠ NOT BOARD-READY — INTERIM STATUS ONLY.**\n>\n"
                f"> **Governance:** reviewer={review_verdict} · "
                f"challenger={challenge_verdict} · "
                "**quant-gate=FAILED** → overall **NOT REVIEW-READY**.\n>\n"
                "> The figures below have NOT been machine-verified. **Treat "
                "every recommendation, euro figure, and “decision required "
                "by” date in this report as PROVISIONAL** — the current "
                "leading option pending reconciliation, **not** a decision the "
                "Board should act on. Deterministic defects still open:\n>\n"
                + defect_lines
                + "\n\n"
                + report
            )
        await _emit(
            engagement_id,
            "quant_tie_out",
            {
                "passed": not unresolved,
                "fixing": False,
                "defects": [d.message for d in unresolved],
            },
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
            # The quant gate's own defects are the MOST actionable lessons
            # available when they exist: they are exact, machine-generated,
            # and never visible to the reviewer (which is told arithmetic is
            # pre-verified and to judge substance only) — so without this
            # section the reflector only ever sees judgment notes and can
            # never learn the mechanical ledger-discipline patterns (missing
            # sources, un-formulated derived values, orphan numbers) that are
            # the actual, recurring cause of interim reports.
            quant_notes = (
                _section(
                    "Quant-gate defects — deterministic, machine-verified "
                    "failures, NOT judgment calls",
                    "\n".join(f"- {d.message}" for d in unresolved),
                )
                if unresolved
                else ""
            )
            focus = (
                "The gates did NOT clear — extract what went wrong in the method."
                if not review_ready
                else "The gates cleared — extract what the reviewer/challenger still "
                "flagged (caveats, near-misses) so the next engagement avoids "
                "even those."
            )
            if quant_notes:
                focus += (
                    " The QUANT GATE specifically failed. Those defects are exact "
                    "and mechanical (a missing source field, a derived value with "
                    "no formula, a number in the report absent from the ledger) — "
                    "prioritize lessons that fix THIS pattern directly (e.g. "
                    "'always give every assumption a source and a plausibility "
                    "band', 'never write a figure in the report that isn't a "
                    "ledger id') over generic analytical advice; these are the "
                    "highest-leverage, most fixable lessons available."
                )
            reflection = await call(
                "reflector",
                REFLECTION_SYSTEM,
                _section("Reviewer notes", review)
                + _section("Challenger notes", challenge)
                + quant_notes
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

    except AllProvidersRateLimitedError as exc:
        # Every provider is rate-limited at once. Don't fail — the work so far
        # is checkpointed in events. Pause, wait for the soonest refill, and
        # resume from where we stopped. The user sees a countdown, not an error.
        # RETRIED (not FAILED) is the honest operational signal: capacity ran
        # out, the run is intact. Pause rate is the metric to alert on.
        telemetry.emit(
            engagement_id,
            "engagement-manager",
            "orchestration",
            "retried",
            retry_count=resume_count + 1,
            metadata={"reason": "all_providers_rate_limited"},
        )
        await _pause_and_resume(
            engagement_id,
            exc,
            case_prompt=case_prompt,
            call=call,
            api_key=api_key,
            model=model,
            images=images,
            resume_count=resume_count,
        )

    except Exception as exc:  # noqa: BLE001 — surface any failure to the client
        message = friendly_error(exc)
        # Operational signal: exception TYPE only, never the message (it can
        # carry case content). The redactor guards metadata, but not sending it
        # is stronger than trusting the guard.
        telemetry.emit(
            engagement_id,
            "engagement-manager",
            "orchestration",
            "failed",
            metadata={"error_type": type(exc).__name__},
        )
        db.set_engagement_status(engagement_id, "failed", error=message)
        await _emit(engagement_id, "engagement_failed", {"error": message})


def _resume_delay(retry_after: float, resume_count: int) -> float:
    """How long to wait before the next resume attempt.

    ``retry_after`` is what the providers advertised, but it is often already
    spent: the failover loop sleeps through the short cooldowns before giving
    up, so by the time it hands back control the remaining wait can read ~0
    while the provider's quota window has NOT actually refilled. Clamping to
    MIN_RESUME_DELAY then would retry every 20 s and burn the whole attempt
    budget in a couple of minutes.

    So back off exponentially per attempt (20 s → 40 s → 80 s …, capped at
    MAX_RESUME_DELAY). Patience is the point: waiting minutes costs nothing —
    the work is checkpointed — whereas exhausting the retries fails a run that
    only needed to sit still.

    The delay is then jittered ±25%. Concurrent engagements share one provider
    quota, so they hit the wall together and would otherwise wake in lockstep,
    collide, and all pause again — a thundering herd that wastes the retry
    budget. Spreading the wake-ups lets them refill in turn.
    """
    base = max(
        config.MIN_RESUME_DELAY, min(float(retry_after), config.MAX_RESUME_DELAY)
    )
    delay = min(base * (2**resume_count), config.MAX_RESUME_DELAY)
    # Clamp AFTER jittering: jittering a capped delay upward would push it past
    # MAX_RESUME_DELAY and quietly break the ceiling (900 s * 1.25 = 1125 s).
    # At the cap the spread becomes one-sided, which is fine — it still breaks
    # up the herd, and erring shorter never violates the bound.
    return min(delay * random.uniform(0.75, 1.25), config.MAX_RESUME_DELAY)


async def _pause_and_resume(
    engagement_id: str,
    exc: AllProvidersRateLimitedError,
    *,
    case_prompt: str,
    call: CallAgent,
    api_key: str | None,
    model: str | None,
    images: list[str] | None,
    resume_count: int,
) -> None:
    """Pause a rate-limited engagement and schedule an automatic resume.

    Completed phases/analysts are already persisted as events, so the resumed
    run reconstructs them and continues from the first unfinished step. The
    BYOK key and any images live only in the scheduled task's closure — never
    persisted — consistent with the never-store-keys guarantee.
    """
    if resume_count >= config.MAX_AUTO_RESUMES:
        message = (
            "AI providers stayed rate-limited across several automatic retries. "
            "Your progress is saved — please reopen this engagement in a little "
            "while and it will finish."
        )
        db.set_engagement_status(engagement_id, "failed", error=message)
        await _emit(engagement_id, "engagement_failed", {"error": message})
        return

    delay = _resume_delay(exc.retry_after, resume_count)
    resume_at = time.time() + delay
    db.set_engagement_status(engagement_id, "paused")
    await _emit(
        engagement_id,
        "engagement_paused",
        {
            "resume_at": resume_at,
            "delay_seconds": round(delay),
            "attempt": resume_count + 1,
            "reason": "All AI providers are refilling their rate limits. This "
            "engagement will resume automatically from where it paused — no "
            "action needed.",
        },
    )
    if not config.AUTO_RESUME:
        return

    async def _resume() -> None:
        try:
            await asyncio.sleep(delay)
            await run_engagement(
                engagement_id,
                case_prompt,
                call=call,
                api_key=api_key,
                model=model,
                images=images,
                resume_count=resume_count + 1,
            )
        except Exception:  # noqa: BLE001 — a resume failure must not crash the loop
            pass

    asyncio.create_task(_resume())


async def recover_interrupted() -> None:
    """Adopt engagements orphaned by a server restart. Called once at startup.

    A pause schedules an in-process task; stopping the process kills it, so a
    paused run would otherwise sit on a countdown that never fires. Now that
    the database survives redeploys, that stall would be permanent.

    Free-tier runs resume on the server's own providers. BYOK runs cannot: the
    user's key was never persisted (by design), and silently finishing them on
    the free chain would downgrade a premium run — so they are closed with an
    honest message instead of quietly resuming at lower quality.

    NOTE: this assumes ONE process owns the database (the current deployment
    runs a single uvicorn worker). Adding ``--workers N`` would make every
    worker adopt the same engagements and run them N times over — gate this
    behind a leader election or a claim on the row before scaling out.
    """
    for row in db.interrupted_engagements():
        engagement_id = row["id"]
        if row["used_byok"]:
            message = (
                "The server restarted while this engagement was running. Your "
                "API key is never stored, so it can't be resumed automatically "
                "— please run it again. Your completed steps are saved below."
            )
            db.set_engagement_status(engagement_id, "failed", error=message)
            await _emit(engagement_id, "engagement_failed", {"error": message})
            continue
        log.info("resuming engagement %s after restart", engagement_id)
        # Images aren't persisted either, so a resumed run continues on the
        # case text alone; already-finished phases keep whatever they saw.
        asyncio.create_task(run_engagement(engagement_id, row["case_prompt"]))
