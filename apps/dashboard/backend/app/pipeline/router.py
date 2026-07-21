"""Task-routing layer — decide the execution target BEFORE provider selection.

ADR-012, **Phase 1 only**: deterministic, rule-based routing. Given a task, a
rule may reorder or filter the failover chain that ``providers.call_with_failover``
is about to walk. This sits *before* provider selection and *reuses* the existing
chain and failover loop — it never builds providers, holds keys, or touches
failover mechanics (cooldowns, pacing, resume-on-rate-limit).

**This phase is intentionally inert in production.** ``_RULES`` ships EMPTY, so
``route()`` returns a no-opinion decision for every task and ``apply_decision()``
returns the chain UNCHANGED — behavior is identical to the pre-router pipeline.
The rule ENGINE and the ``RoutingDecision`` contract are what Phase 1 delivers;
the actual routing rules (ADR-012 §6.1 guardrails, §6.2/§6.3 categories) are
added in later, separately-approved phases.

Backward-compatibility contract (ADR-012 §13 P1):
- No rule matches  → chain returned UNCHANGED, failover runs exactly as before.
- A rule that would empty the chain → ignored (never strand the caller).
- Input chain is never mutated; provider objects are shared, not copied.

NOT in Phase 1 (deliberately absent — do not add here without the matching ADR
phase): capability scoring, live cost/latency signals, LLM-based routing. Every
rule is a pure, deterministic function of the task descriptor.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.pipeline import registry

if TYPE_CHECKING:
    from app.pipeline.providers import Provider

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TaskDescriptor:
    """What the router is allowed to know about a call, to decide its routing.

    Deliberately small and cheap: routing an LLM call must never cost an LLM
    call (ADR-012 §12). ``agent_name`` is a signal; the capability signals
    (``has_images``, ``prompt_size``, ``needs_json``) are what the Provider
    Router's capability rules actually match against the registry.
    """

    agent_name: str
    has_images: bool = False
    prompt_size: int | None = None  # approx input tokens if known; None = unknown
    needs_json: bool = False  # caller declares it needs reliable structured JSON


@dataclass(frozen=True)
class RoutingDecision:
    """An ordering/filter over the failover chain — NOT a new transport.

    Two ways to express a preference; a rule sets whichever fits:

    - **By family** (`preferred_families` / `excluded_families`): move/drop named
      provider families. Kept for family-level policy (e.g. BYOK).
    - **By capability** (`prefer_flags` / `min_context`): float providers whose
      *model* (per the registry) satisfies a capability to the front — no
      provider-family names embedded. `prefer_flags` names boolean `ModelSpec`
      flags (e.g. ``supports_vision``); `min_context` requires the model's usable
      context to be ≥ N tokens. This is how capability-driven routing (P3+)
      avoids hardcoding which providers can do what.

    ``rule_name`` / ``rationale`` are observability. An empty decision means "no
    opinion": the chain is used exactly as-is (the default, backward-compatible
    state). Every form is a PREFERENCE that reorders — failover always follows.
    """

    preferred_families: tuple[str, ...] = ()
    excluded_families: tuple[str, ...] = ()
    prefer_flags: tuple[str, ...] = ()  # boolean ModelSpec flags to prefer
    min_context: int | None = None  # prefer models whose usable context ≥ this
    rule_name: str | None = None
    rationale: str = ""

    @property
    def is_no_opinion(self) -> bool:
        return (
            not self.preferred_families
            and not self.excluded_families
            and not self.prefer_flags
            and self.min_context is None
        )


# A rule inspects the task and either claims it (returns a decision) or passes
# (returns None, letting the next rule try). Pure and deterministic — same task
# in, same decision out, always (ADR-012 §5.1 "deterministic routing rules").
Rule = Callable[[TaskDescriptor], "RoutingDecision | None"]


# ---- Provider Router capability rules (ADR-012 §6.3) ---------------------
#
# Each rule keys on an intrinsic property of ONE call and expresses a
# CAPABILITY preference (not a provider-family name). ``apply_decision``
# resolves each capability against the registry (a provider's model → its
# ``ModelSpec`` flags), so adding a vision/JSON-capable provider or model needs
# only a registry entry — no rule edit. Every rule is a PREFERENCE that
# reorders: if no provider satisfies it, the chain is unchanged and the existing
# failover serves the call exactly as today (fail-open, failover intact).

# A prompt at or above this many (approx) input tokens is "long-context": steer
# it away from providers whose usable window can't hold it (e.g. GitHub Models'
# 8k free-tier cap) before a wasted round-trip. Set safely below that 8k cap.
_LONG_CONTEXT_THRESHOLD = 6000


def _vision_rule(task: TaskDescriptor) -> RoutingDecision | None:
    """Prefer providers whose model `supports_vision` when the call has images.

    Capability-driven (P3): the decision names the ``supports_vision`` flag, and
    ``apply_decision`` reads each provider's model from the registry — so a
    vision-capable Ollama model (e.g. ``gemma3``) is preferred automatically,
    while a text-only local model (``qwen3``) is not. No provider-family names.
    Returns ``None`` for a text-only call, leaving the chain untouched.
    """
    if not task.has_images:
        return None
    return RoutingDecision(
        prefer_flags=("supports_vision",),
        rule_name="vision",
        rationale=(
            "call carries images → prefer providers whose model supports "
            "vision (per registry) so the image is read, not silently dropped"
        ),
    )


def _long_context_rule(task: TaskDescriptor) -> RoutingDecision | None:
    """Prefer providers whose usable context can hold a large prompt.

    Fires only above ``_LONG_CONTEXT_THRESHOLD`` — small prompts get no opinion,
    so ordinary calls are untouched. ``apply_decision`` compares each provider's
    ``effective_context`` (registry, tier-cap aware) against ``min_context``.
    """
    if task.prompt_size is None or task.prompt_size < _LONG_CONTEXT_THRESHOLD:
        return None
    return RoutingDecision(
        min_context=task.prompt_size,
        rule_name="long-context",
        rationale=(
            f"large prompt (~{task.prompt_size} tokens) → prefer providers whose "
            "usable context can hold it; avoids tier-capped providers (e.g. "
            "GitHub 8k) that would reject it"
        ),
    )


def _json_rule(task: TaskDescriptor) -> RoutingDecision | None:
    """Prefer providers whose model reliably emits structured JSON.

    Keyed on the caller-declared ``needs_json`` (there is no reliable per-call
    JSON signal at the seam, so this activates when a caller opts in). Returns
    ``None`` otherwise, leaving the chain untouched.
    """
    if not task.needs_json:
        return None
    return RoutingDecision(
        prefer_flags=("supports_json",),
        rule_name="structured-json",
        rationale=(
            "call needs structured JSON → prefer providers whose model "
            "reliably emits JSON (per registry)"
        ),
    )


# Active production rules, tried in order (a priority ranking — first match
# wins, so one capability applies per call). Kept module-level so it is
# trivially monkeypatchable in tests and overridable by a caller passing its
# own ``rules`` to ``route``. Adding a rule requires its own ADR-012 phase.
_RULES: list[Rule] = [_vision_rule, _long_context_rule, _json_rule]


def route(task: TaskDescriptor, rules: Sequence[Rule] | None = None) -> RoutingDecision:
    """First matching rule wins; if none match, return a no-opinion decision.

    Rules are tried in order (a rule list is a priority ranking). The first one
    to return a non-``None`` decision claims the task; later rules are not
    consulted. With the default (empty) ``_RULES`` this always returns a
    no-opinion ``RoutingDecision`` — the Phase-1 identity behavior.

    **Fail-open (ADR-012 §12).** A rule that raises must never fail the request:
    the exception is logged and swallowed, that rule is skipped, and evaluation
    continues with the next rule. If no rule then claims the task, the result is
    a no-opinion decision — i.e. the unrouted chain — so a buggy rule degrades to
    exactly today's behavior instead of taking down the call. Routing is an
    optimization; it is never allowed to become a new failure domain.
    """
    for rule in _RULES if rules is None else rules:
        try:
            decision = rule(task)
        except Exception:  # noqa: BLE001 — a bad rule must not fail the request
            log.warning(
                "routing rule %r raised on %s — skipping it, using the unrouted chain",
                getattr(rule, "__name__", rule),
                task.agent_name,
                exc_info=True,
            )
            continue
        if decision is not None:
            return decision
    return RoutingDecision()


def _provider_satisfies(provider: Provider, decision: RoutingDecision) -> bool:
    """Whether a live provider meets a decision's CAPABILITY preference.

    Capabilities are resolved from the registry via the provider's model id, so
    no provider-family knowledge is embedded here. When the model isn't
    registered (e.g. an env override), a boolean flag falls back to the live
    provider's own attribute if it carries one (``Provider.supports_vision``);
    an unknown context is treated as not-satisfying (safe: the provider simply
    isn't floated up, and failover still reaches it).
    """
    for flag in decision.prefer_flags:
        has = registry.model_supports(provider.model, flag)
        if has is None:  # unregistered model → fall back to the live flag
            has = bool(getattr(provider, flag, False))
        if not has:
            return False
    if decision.min_context is not None:
        ctx = registry.effective_context(provider.model)
        if ctx is None or ctx < decision.min_context:
            return False
    return True


def apply_decision(chain: list[Provider], decision: RoutingDecision) -> list[Provider]:
    """Return a chain ordered/filtered per ``decision`` — never mutating input.

    Guarantees (ADR-012 §13 P1):
    - No opinion → the SAME chain, unchanged (identity).
    - Excluding every provider is treated as a misconfigured rule: the original
      chain is returned rather than stranding the caller with no providers.
    - Provider objects are shared (so their live cooldown/pacing state is the
      same objects the failover loop already knows) — only their ORDER differs.

    All ordering is stable: family preferences apply first (by declared order),
    then capability preferences float satisfying providers to the front; every
    unmatched provider keeps its original relative position (so ``_ordered``'s
    intra-family key-selection still applies afterward). Capability preferences
    are advisory reorders — if NO provider satisfies, the order is unchanged
    (fail-open), never emptied.
    """
    if decision.is_no_opinion:
        return chain

    kept = [p for p in chain if p.family not in decision.excluded_families]
    if not kept:
        # A rule that filters the whole chain away is a bug in the rule, not a
        # valid instruction to fail the call. Fall back to the full chain.
        return chain

    if decision.preferred_families:
        rank = {family: i for i, family in enumerate(decision.preferred_families)}
        unranked = len(rank)
        # sorted() is stable: unranked families (all keyed ``unranked``) retain
        # their original order; ranked families sort to the front by index.
        kept = sorted(kept, key=lambda p: rank.get(p.family, unranked))

    if decision.prefer_flags or decision.min_context is not None:
        # Stable: providers satisfying the capability sort to the front (key 0),
        # the rest keep their relative order (key 1). If none satisfy, all get
        # key 1 → order unchanged (fail-open).
        kept = sorted(kept, key=lambda p: 0 if _provider_satisfies(p, decision) else 1)

    return kept


def _log_routing_decision(
    task: TaskDescriptor,
    decision: RoutingDecision,
    before: list[Provider],
    after: list[Provider],
) -> None:
    """Emit one lightweight DEBUG line per routing decision (ADR-012 §12).

    Records the four things a routing decision is judged by: the matched
    capability, the selected provider order, the reason, and the fallback
    status. DEBUG level so it is opt-in via log config and adds no noise to a
    normal run. No metrics backend, no dashboard — just the project logger.

    Fallback status:
    - ``unrouted``  — no rule matched; the chain is used as-is.
    - ``applied``   — a rule matched and changed the provider order.
    - ``fell-open`` — a rule matched but no provider satisfied it, so the chain
                      is unchanged (the fail-open path).
    """
    if decision.is_no_opinion:
        matched, reason, status = "none", "no rule matched", "unrouted"
    else:
        matched = decision.rule_name or "unnamed"
        reason = decision.rationale
        reordered = [p.name for p in before] != [p.name for p in after]
        status = "applied" if reordered else "fell-open"
    log.debug(
        "route agent=%s matched=%s status=%s selected=%s reason=%s",
        task.agent_name,
        matched,
        status,
        [p.name for p in after][:6],
        reason,
    )


def route_chain(
    chain: list[Provider],
    task: TaskDescriptor,
    rules: Sequence[Rule] | None = None,
) -> list[Provider]:
    """Convenience: ``apply_decision(chain, route(task))`` in one call, with a
    lightweight routing-telemetry log line.

    This is the single entry point ``providers.call_with_failover`` uses. With
    the default empty ruleset / no capable provider it is an identity function
    over ``chain``.
    """
    decision = route(task, rules)
    out = apply_decision(chain, decision)
    _log_routing_decision(task, decision, chain, out)
    return out
