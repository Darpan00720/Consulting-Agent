"""Workflow Router — classify a unit of work and SELECT its owning target.

ADR-013 W1 (finalized in W1.1 to close the independent review). This is a
**pure, deterministic, synchronous** function ``route(work, context) ->
WorkflowDecision``: no side effects beyond one debug log line, no dispatch, no
orchestration, and it never calls a target's ``invoke`` — the host (Claude
Flow) owns dispatch (ADR-013 §2a). Classification is rule-based; no LLM.

Selection pipeline (ADR-013 §2, §6.4, §8):
  consulting-domain guardrail (runs FIRST, independent of the classifier and of
  any category hint) → else classify → apply category guardrails (independent of
  the target registry) → pick the first available target in priority order.

**Routing never crashes (ADR-013 §7).** Every step — classification, selection,
and target inspection (`can_handle`/`available`) — is guarded; on any error the
router fails open to a safe decision (a governed category still hard-blocks
rather than leaking to a dev tool) and records the failure reason. Routing is
never a new failure domain.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field, replace

from app.workflow.targets import (
    Target,
    WorkflowCategory,
    default_registry,
)

log = logging.getLogger(__name__)

_C = WorkflowCategory


# ---- Inputs / outputs (ADR-013 §6, §6a) ----------------------------------


@dataclass(frozen=True)
class Work:
    """One unit of work + its classification signals (ADR-013 §6a).

    All fields are explicit signals — no prompt, no LLM input. ``text`` is the
    caller's stated intent; the rest are stronger, authoritative signals.
    """

    text: str = ""
    command: str | None = None  # invoked slash command, e.g. "/codex:review"
    skill: str | None = None  # requested skill, e.g. "solve-case"
    agent: str | None = None  # explicitly requested agent
    files: tuple[str, ...] = ()  # file paths touched
    category_hint: str | None = None  # explicit --category override


@dataclass(frozen=True)
class RoutingContext:
    """Routing state threaded through a unit of work (ADR-013 §6a).

    Lives in this value, never a global. ``classified`` makes re-entry
    idempotent.

    ``dispatch_depth`` — OWNERSHIP (ADR-013 §6a, clarified in W1.1):

        Workflow Router (validates)  →  Host  →  Dispatcher (enforces)

    The router is pure and has no dispatch to guard, so it **never enforces**
    the depth cap. It only *carries* the counter and *exposes* a pure
    validation helper (:func:`exceeds_dispatch_cap`). The **host increments**
    it per nested unit and **enforces** the cap before dispatching. No
    dispatcher logic lives in this module.
    """

    trace_id: str
    category: WorkflowCategory | None = None
    classified: bool = False
    dispatch_depth: int = 0


@dataclass(frozen=True)
class WorkflowDecision:
    """What the router emits; the HOST consumes it and dispatches (ADR-013 §2a).

    Telemetry metadata (ADR-013 §2/§12, W1.1): ``trace_id`` is on
    ``routing_context``; ``fallback_used`` and ``failure_reason`` are exposed
    here so the host and logs can correlate and audit without any tracing
    backend.
    """

    category: WorkflowCategory
    selected_target: str | None  # None = guardrail-blocked / no target available
    fallback_targets: tuple[str, ...] = ()
    guardrail_verdict: str = "ok"
    fallback_used: bool = False
    failure_reason: str | None = None
    routing_context: RoutingContext = field(
        default_factory=lambda: RoutingContext(trace_id="")
    )
    reason: str = ""


# ---- dispatch-depth: router validates, host enforces (ADR-013 §6a, item C) --

MAX_DISPATCH_DEPTH = 8


def exceeds_dispatch_cap(context: RoutingContext) -> bool:
    """Pure validation helper the HOST calls before dispatching (ADR-013 §6a).

    The Workflow Router never enforces this (it has no dispatch); it only lets
    the host check the cap it owns. Returns True when a nested unit has gone too
    deep and the host should refuse to start another.
    """
    return context.dispatch_depth > MAX_DISPATCH_DEPTH


# ---- Robust, deterministic phrase matching (ADR-013 §7, item D) -----------

_NEGATORS = frozenset(
    {"not", "no", "never", "without", "avoid", "don't", "dont", "cannot", "can't"}
)


def _phrase_hit(text: str, phrase: str) -> bool:
    """Word-boundary match for ``phrase`` in already-lowercased ``text``,
    skipping negated occurrences.

    Word boundaries stop 'undocumented' matching 'document' and 'reviewer'
    matching 'review'. A match whose two preceding words include a negator
    ('do not research') is skipped. Deterministic — no LLM.
    """
    for m in re.finditer(rf"\b{re.escape(phrase)}\b", text):
        preceding = text[: m.start()].split()[-2:]
        if any(w.strip(".,!?;:") in _NEGATORS for w in preceding):
            continue
        return True
    return False


def _contains_any(text: str, phrases: tuple[str, ...]) -> str | None:
    """Return the first (word-boundary, non-negated) phrase that hits, or None."""
    lowered = text.lower()
    for phrase in phrases:
        if _phrase_hit(lowered, phrase):
            return phrase
    return None


# ---- A. Consulting-domain guardrail detector (runs FIRST) -----------------
#
# ADR-013 §6.4/§8 + ADR-010 §6c: consulting-domain work must go to governed
# agents ONLY. This detector runs BEFORE ordinary category selection and is
# INDEPENDENT of the classifier output, the category hint, and routing
# precedence — so a narrow-keyword miss or a conflicting hint can never leak
# consulting work to a dev/general target. When it fires, the guardrailed
# BUSINESS_CONSULTING category owns routing.

_CONSULTING_SKILLS = frozenset({"solve-case"})
_CONSULTING_COMMANDS = frozenset({"/solve-case"})
_CONSULTING_AGENTS = frozenset(
    {
        "case-classifier",
        "framework-selector",
        "framework-strategist",
        "issue-tree-generator",
        "financial-analyst",
        "market-analyst",
        "operations-analyst",
        "strategy-analyst",
        "risk-analyst",
        "knowledge-agent",
        "knowledge-curator",
        "information-gap",
        "planner",
    }
)
# Consulting-domain phrases (the review's false-negative set + the archetypes).
_CONSULTING_PHRASES: tuple[str, ...] = (
    "business strategy",
    "market entry",
    "market sizing",
    "go-to-market",
    "pricing strategy",
    "pricing",
    "profitability",
    "cost reduction",
    "growth strategy",
    "turnaround",
    "due diligence",
    "operating model",
    "transformation",
    "organizational design",
    "org design",
    "restructuring",
    "executive recommendation",
    "m&a",
    "merger",
    "acquisition",
    "competitive strategy",
    "value chain",
    "consulting framework",
    "business case",
)


def is_consulting_domain(work: Work) -> tuple[bool, str]:
    """Deterministically detect consulting-domain intent (returns (hit, signal)).

    Independent of the classifier and of ``category_hint`` — it reads only the
    explicit skill/command/agent signals and the consulting-domain phrase set.
    """
    if work.skill in _CONSULTING_SKILLS:
        return True, f"skill '{work.skill}'"
    if work.command in _CONSULTING_COMMANDS:
        return True, f"command {work.command}"
    if work.agent in _CONSULTING_AGENTS:
        return True, f"agent '{work.agent}'"
    phrase = _contains_any(work.text, _CONSULTING_PHRASES)
    if phrase is not None:
        return True, f"phrase '{phrase}'"
    return False, ""


# ---- Classification rules (explicit signals, ADR-013 §11) ----------------

_COMMAND_CATEGORY: dict[str, WorkflowCategory] = {
    "/codex:review": _C.CODE_REVIEW,
    "/codex:adversarial-review": _C.CODE_REVIEW,
    "/code-review": _C.CODE_REVIEW,
    "/security-review": _C.CODE_REVIEW,
    "/codex:rescue": _C.DEBUGGING,
}

_SKILL_CATEGORY: dict[str, WorkflowCategory] = {
    "code-review": _C.CODE_REVIEW,
}

_AGENT_CATEGORY: dict[str, WorkflowCategory] = {
    "report-writer": _C.DOCUMENTATION,
    "knowledge-curator": _C.DOCUMENTATION,
}

# Intent keywords (lowest-confidence signal), matched by word boundary.
_INTENT_KEYWORDS: dict[WorkflowCategory, tuple[str, ...]] = {
    _C.CODE_REVIEW: ("code review", "review this", "adversarial review"),
    _C.DEBUGGING: (
        "debug",
        "root cause",
        "failing test",
        "stack trace",
        "fix the bug",
    ),
    _C.REPOSITORY_ANALYSIS: (
        "dependency graph",
        "call graph",
        "codebase structure",
        "analyze the repo",
    ),
    _C.RESEARCH: ("research", "investigate", "look up", "find out about"),
    _C.DOCUMENTATION: ("document", "write docs", "readme", "changelog", "write an adr"),
    _C.CODING: ("implement", "refactor", "scaffold", "write code", "add a function"),
}

# Deterministic tie-break when intent matches several categories (ADR-013 §7).
_TIEBREAK_ORDER: tuple[WorkflowCategory, ...] = (
    _C.CODE_REVIEW,
    _C.DEBUGGING,
    _C.REPOSITORY_ANALYSIS,
    _C.RESEARCH,
    _C.DOCUMENTATION,
    _C.CODING,
)

_DOC_EXT = {".md", ".rst", ".txt", ".adoc"}
_CODE_EXT = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".rs",
    ".java",
    ".c",
    ".cpp",
    ".rb",
}


def _classify_intent(text: str) -> tuple[WorkflowCategory | None, tuple[str, ...]]:
    """Return (winning category, losing categories) from intent keywords."""
    matched = [
        cat
        for cat, kws in _INTENT_KEYWORDS.items()
        if _contains_any(text, kws) is not None
    ]
    for cat in _TIEBREAK_ORDER:
        if cat in matched:
            losers = tuple(c.value for c in matched if c is not cat)
            return cat, losers
    return None, ()


def _classify_files(files: tuple[str, ...]) -> WorkflowCategory | None:
    exts = {os.path.splitext(f)[1].lower() for f in files}
    if exts & _DOC_EXT and not (exts & _CODE_EXT):
        return _C.DOCUMENTATION
    if exts & _CODE_EXT:
        return _C.CODING
    return None


def classify(work: Work) -> tuple[WorkflowCategory, str]:
    """Rule-based classification, explicit signals first (ADR-013 §11).

    Precedence: --category hint → command → skill → agent → intent keywords →
    file types → default (general reasoning). Consulting-domain detection is
    NOT here — it runs earlier and independently (see ``route``). Returns
    (category, reason).
    """
    if work.category_hint is not None:
        try:
            return WorkflowCategory(work.category_hint), (
                f"explicit category hint '{work.category_hint}'"
            )
        except ValueError:
            pass  # unknown hint → fall through to weaker signals

    if work.command and work.command in _COMMAND_CATEGORY:
        return _COMMAND_CATEGORY[work.command], f"invoked command {work.command}"

    if work.skill and work.skill in _SKILL_CATEGORY:
        return _SKILL_CATEGORY[work.skill], f"requested skill '{work.skill}'"

    if work.agent and work.agent in _AGENT_CATEGORY:
        return _AGENT_CATEGORY[work.agent], f"requested agent '{work.agent}'"

    intent, losers = _classify_intent(work.text)
    if intent is not None:
        note = f" (over {', '.join(losers)})" if losers else ""
        return intent, f"intent keyword → {intent.value}{note}"

    by_file = _classify_files(work.files)
    if by_file is not None:
        return by_file, f"file types → {by_file.value}"

    return _C.GENERAL_REASONING, "no explicit signal — default"


# ---- Selection + guardrails (ADR-013 §2, §6.4, §8) -----------------------

# Category → target names, in preference order (the ADR-013 §4 map, as data).
_CATEGORY_PRIORITY: dict[WorkflowCategory, tuple[str, ...]] = {
    _C.CODING: ("codex", "claude"),
    _C.DEBUGGING: ("codex", "claude"),
    _C.CODE_REVIEW: ("codex", "claude"),
    _C.DOCUMENTATION: ("claude", "codex"),
    _C.REPOSITORY_ANALYSIS: ("repository_analysis", "claude"),
    _C.RESEARCH: ("claude",),
    _C.BUSINESS_CONSULTING: ("consulting",),
    _C.GENERAL_REASONING: ("claude",),
}

# Guardrailed categories → the ONLY target names allowed to own them. Enforced
# INDEPENDENT of target registration (ADR-013 §8): a rogue target claiming a
# guardrailed category can never be selected for it.
_GOVERNED: dict[WorkflowCategory, frozenset[str]] = {
    _C.BUSINESS_CONSULTING: frozenset({"consulting"}),
}


def _safe_can_handle(target: Target, category: WorkflowCategory) -> bool:
    try:
        return bool(target.can_handle(category))
    except Exception:  # noqa: BLE001 — a malformed target is skipped, not fatal
        return False


def _safe_available(target: Target) -> bool:
    try:
        return bool(target.available())
    except Exception:  # noqa: BLE001 — a failing probe means "not available now"
        return False


def _select(
    category: WorkflowCategory, registry: dict[str, Target]
) -> tuple[str | None, tuple[str, ...], str, bool]:
    """Pick the first available target for a category. Returns
    (selected, fallbacks, guardrail_verdict, fallback_used). Never raises —
    each target inspection is guarded (ADR-013 §7)."""
    claiming = {name for name, t in registry.items() if _safe_can_handle(t, category)}
    priority = _CATEGORY_PRIORITY.get(category, ())
    ordered = [n for n in priority if n in claiming]
    ordered += sorted(claiming - set(ordered))  # extras, deterministically

    allow = _GOVERNED.get(category)
    if allow is not None:
        # Guardrail: independent of registration — restrict to the allow-list.
        ordered = [n for n in ordered if n in allow]

    available = [n for n in ordered if _safe_available(registry[n])]
    primary = priority[0] if priority else None

    if not available:
        if allow is not None:
            return (
                None,
                (),
                (
                    f"blocked: {category.value} requires a governed agent "
                    f"({', '.join(sorted(allow))}); none available"
                ),
                False,
            )
        return None, (), f"blocked: no available target for {category.value}", False

    selected = available[0]
    return selected, tuple(available[1:]), "ok", selected != primary


# ---- route(): pure, fail-open entry point (ADR-013 §2a, §7) --------------


def route(
    work: Work,
    context: RoutingContext,
    registry: dict[str, Target] | None = None,
) -> WorkflowDecision:
    """Classify + select for one unit of work — pure, no dispatch (ADR-013 §2a).

    Never raises (ADR-013 §7): any failure in classification/selection produces
    a safe fail-open decision instead. Consulting-domain work still hard-blocks
    on failure rather than leaking to a dev tool.
    """
    reg = default_registry() if registry is None else registry
    try:
        return _route_inner(work, context, reg)
    except Exception as exc:  # noqa: BLE001 — routing must never crash
        return _fail_open(work, context, reg, exc)


def _route_inner(
    work: Work, context: RoutingContext, reg: dict[str, Target]
) -> WorkflowDecision:
    if context.classified and context.category is not None:
        category = context.category
        reason = "already classified (idempotent re-entry)"
    else:
        is_consulting, signal = is_consulting_domain(work)
        if is_consulting:
            category = _C.BUSINESS_CONSULTING
            reason = f"consulting domain detected ({signal}) — guardrail owns routing"
        else:
            category, reason = classify(work)

    selected, fallbacks, verdict, fallback_used = _select(category, reg)
    decision = WorkflowDecision(
        category=category,
        selected_target=selected,
        fallback_targets=fallbacks,
        guardrail_verdict=verdict,
        fallback_used=fallback_used,
        failure_reason=None,
        routing_context=replace(context, category=category, classified=True),
        reason=reason,
    )
    _log_decision(decision)
    return decision


def _fail_open(
    work: Work, context: RoutingContext, reg: dict[str, Target], exc: Exception
) -> WorkflowDecision:
    """Safe decision when routing itself errors (ADR-013 §7). A governed
    category still hard-blocks — it must not leak to a dev tool even on failure."""
    failure = f"{type(exc).__name__}: {exc}"
    try:
        consulting, _ = is_consulting_domain(work)
    except Exception:  # noqa: BLE001 — even detection is guarded
        consulting = False

    if consulting:
        category = _C.BUSINESS_CONSULTING
        selected, fallbacks, verdict = (
            None,
            (),
            ("blocked: consulting requires a governed agent (routing failed open)"),
        )
    else:
        category = _C.GENERAL_REASONING
        selected, fallbacks, verdict = _safe_default(reg)

    decision = WorkflowDecision(
        category=category,
        selected_target=selected,
        fallback_targets=fallbacks,
        guardrail_verdict=verdict,
        fallback_used=True,
        failure_reason=failure,
        routing_context=replace(context, category=category, classified=True),
        reason=f"routing error — failed open to {category.value}",
    )
    _log_decision(decision)
    return decision


def _safe_default(reg: dict[str, Target]) -> tuple[str | None, tuple[str, ...], str]:
    """General-reasoning fallback (Claude), fully guarded."""
    for name in _CATEGORY_PRIORITY.get(_C.GENERAL_REASONING, ("claude",)):
        target = reg.get(name)
        if target is not None and _safe_available(target):
            return name, (), "ok"
    return None, (), "blocked: no available default target"


def _log_decision(decision: WorkflowDecision) -> None:
    """Log the decision metadata (ADR-013 §12, W1.1): trace_id, category,
    target, fallback_used, failure_reason, reason. No dispatch logging — dispatch
    isn't ours to log."""
    log.debug(
        "workflow-route trace_id=%s category=%s target=%s fallback_used=%s "
        "failure_reason=%s reason=%s",
        decision.routing_context.trace_id,
        decision.category.value,
        decision.selected_target,
        decision.fallback_used,
        decision.failure_reason,
        decision.reason,
    )
