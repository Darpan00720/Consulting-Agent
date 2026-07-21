"""Tests for the task-routing layer (ADR-012, Phase 1 — deterministic rules).

The load-bearing guarantee this phase makes is *backward compatibility*: with
the default (empty) ruleset the router is an identity function over the chain,
so the whole pre-router pipeline behaves exactly as before. These tests pin
that guarantee, plus the rule-engine and chain-rewrite mechanics that Phase 2
will build real rules on top of.
"""

from __future__ import annotations

import asyncio

from app.pipeline import providers, router


def _provider(
    name: str, *, model: str = "test-model", supports_vision: bool = False
) -> providers.Provider:
    """A real Provider (so `.family` behaves exactly as in production).

    ``model``/``supports_vision`` let capability tests exercise registry-driven
    routing: pass a registered ``model`` to resolve capabilities from the
    registry, or set ``supports_vision`` to use the live-flag fallback path.
    """
    return providers.Provider(
        name=name,
        base_url="http://test.invalid",
        api_key="test-key",
        model=model,
        min_gap=0.0,
        cooldown_429=1.0,
        supports_vision=supports_vision,
    )


# ---- RoutingDecision contract -------------------------------------------


def test_empty_decision_is_no_opinion():
    assert router.RoutingDecision().is_no_opinion is True


def test_decision_with_preferred_is_an_opinion():
    assert router.RoutingDecision(preferred_families=("ollama",)).is_no_opinion is False


def test_decision_with_excluded_is_an_opinion():
    assert router.RoutingDecision(excluded_families=("github",)).is_no_opinion is False


# ---- route(): rule engine ------------------------------------------------


def test_production_ruleset_is_the_capability_rules_in_priority_order():
    """The Provider Router's active capability rules, first-match priority order.
    Any other entry landing in _RULES without its own ADR-012 phase is a real
    regression."""
    expected = [router._vision_rule, router._long_context_rule, router._json_rule]
    assert list(router._RULES) == expected


def test_route_non_matching_task_returns_no_opinion():
    decision = router.route(router.TaskDescriptor(agent_name="anything"))
    assert decision.is_no_opinion


def test_real_consulting_agents_get_no_opinion():
    """The live product agents issue text-only calls (no images), so the
    production ruleset must leave every one of them on the unrouted chain
    (backward compat) — vision is the only active rule and it keys on images."""
    for agent in (
        "case-classifier",
        "information-gap",
        "planner",
        "framework-selector",
        "issue-tree-generator",
        "knowledge-agent",
        "financial-analyst",
        "market-analyst",
        "operations-analyst",
        "strategy-analyst",
        "risk-analyst",
        "reviewer",
        "challenger",
        "report-writer",
        "knowledge-curator",
        "engagement-manager",
        "grader",
    ):
        assert router.route(router.TaskDescriptor(agent_name=agent)).is_no_opinion


def test_route_first_matching_rule_wins():
    def rule_a(_task):
        return router.RoutingDecision(preferred_families=("a",), rule_name="a")

    def rule_b(_task):  # would also match, but a wins
        return router.RoutingDecision(preferred_families=("b",), rule_name="b")

    decision = router.route(
        router.TaskDescriptor(agent_name="t"), rules=[rule_a, rule_b]
    )
    assert decision.rule_name == "a"


def test_route_skips_non_matching_rules():
    def passes(_task):
        return None  # does not claim the task

    def claims(_task):
        return router.RoutingDecision(preferred_families=("z",), rule_name="z")

    decision = router.route(
        router.TaskDescriptor(agent_name="t"), rules=[passes, claims]
    )
    assert decision.rule_name == "z"


def test_route_all_rules_pass_returns_no_opinion():
    decision = router.route(
        router.TaskDescriptor(agent_name="t"), rules=[lambda _t: None]
    )
    assert decision.is_no_opinion


def test_route_rule_can_read_task_fields():
    def vision_rule(task):
        if task.has_images:
            return router.RoutingDecision(preferred_families=("gemini",))
        return None

    with_img = router.route(
        router.TaskDescriptor(agent_name="t", has_images=True), rules=[vision_rule]
    )
    without_img = router.route(
        router.TaskDescriptor(agent_name="t", has_images=False), rules=[vision_rule]
    )
    assert with_img.preferred_families == ("gemini",)
    assert without_img.is_no_opinion


# ---- apply_decision(): chain rewrite -------------------------------------


def test_apply_no_opinion_returns_chain_unchanged():
    chain = [_provider("gemini"), _provider("cerebras")]
    out = router.apply_decision(chain, router.RoutingDecision())
    assert out is chain  # identity — same object, untouched


def test_apply_preferred_moves_family_to_front():
    chain = [_provider("gemini"), _provider("cerebras"), _provider("ollama")]
    out = router.apply_decision(
        chain, router.RoutingDecision(preferred_families=("ollama",))
    )
    assert [p.name for p in out] == ["ollama", "gemini", "cerebras"]


def test_apply_preferred_preserves_remainder_order():
    """Non-preferred families keep their ORIGINAL relative order (stable sort)."""
    chain = [_provider("gemini"), _provider("cerebras"), _provider("github")]
    out = router.apply_decision(
        chain, router.RoutingDecision(preferred_families=("github",))
    )
    assert [p.name for p in out] == ["github", "gemini", "cerebras"]


def test_apply_preferred_orders_multiple_families_by_declared_order():
    chain = [_provider("a"), _provider("b"), _provider("c")]
    out = router.apply_decision(
        chain, router.RoutingDecision(preferred_families=("c", "a"))
    )
    assert [p.name for p in out] == ["c", "a", "b"]


def test_apply_preferred_family_absent_is_noop_for_that_family():
    chain = [_provider("gemini"), _provider("cerebras")]
    out = router.apply_decision(
        chain, router.RoutingDecision(preferred_families=("ollama",))
    )
    assert [p.name for p in out] == ["gemini", "cerebras"]


def test_apply_excluded_removes_family():
    chain = [_provider("gemini"), _provider("github"), _provider("cerebras")]
    out = router.apply_decision(
        chain, router.RoutingDecision(excluded_families=("github",))
    )
    assert [p.name for p in out] == ["gemini", "cerebras"]


def test_apply_preserves_intra_family_order():
    """Multiple keys in one family keep their order so `_ordered` can still pick
    the soonest-ready sibling afterward."""
    chain = [_provider("gemini"), _provider("gemini#2"), _provider("cerebras")]
    out = router.apply_decision(
        chain, router.RoutingDecision(preferred_families=("gemini",))
    )
    assert [p.name for p in out] == ["gemini", "gemini#2", "cerebras"]


def test_apply_excluding_whole_chain_falls_back_to_original():
    """A rule that filters everything away is a bug in the rule, not a valid
    'fail the call' instruction — the caller must not be stranded."""
    chain = [_provider("gemini"), _provider("cerebras")]
    out = router.apply_decision(
        chain, router.RoutingDecision(excluded_families=("gemini", "cerebras"))
    )
    assert out is chain


def test_apply_never_mutates_input_chain():
    chain = [_provider("gemini"), _provider("cerebras"), _provider("ollama")]
    before = [p.name for p in chain]
    router.apply_decision(
        chain,
        router.RoutingDecision(
            preferred_families=("ollama",), excluded_families=("gemini",)
        ),
    )
    assert [p.name for p in chain] == before  # original untouched


def test_apply_combined_exclude_then_prefer():
    chain = [_provider("gemini"), _provider("github"), _provider("ollama")]
    out = router.apply_decision(
        chain,
        router.RoutingDecision(
            preferred_families=("ollama",), excluded_families=("github",)
        ),
    )
    assert [p.name for p in out] == ["ollama", "gemini"]


# ---- fail-open: a raising rule must never fail the request (ADR-012 §12) --


def _boom_rule(_task):
    raise RuntimeError("rule blew up")


def test_route_swallows_a_raising_rule_and_returns_no_opinion():
    """A lone rule that raises degrades to the unrouted chain, not a failure."""
    decision = router.route(router.TaskDescriptor(agent_name="t"), rules=[_boom_rule])
    assert decision.is_no_opinion


def test_route_skips_a_raising_rule_and_tries_the_next():
    """One rule raising must not stop a later, healthy rule from claiming."""

    def claims(_task):
        return router.RoutingDecision(preferred_families=("ollama",), rule_name="ok")

    decision = router.route(
        router.TaskDescriptor(agent_name="t"), rules=[_boom_rule, claims]
    )
    assert decision.rule_name == "ok"
    assert decision.preferred_families == ("ollama",)


def test_route_logs_a_warning_when_a_rule_raises(caplog):
    """The swallowed exception is surfaced as a lightweight warning, not silent."""
    with caplog.at_level("WARNING", logger="app.pipeline.router"):
        router.route(router.TaskDescriptor(agent_name="classifier"), rules=[_boom_rule])
    assert any("_boom_rule" in r.message for r in caplog.records)
    assert any(r.levelname == "WARNING" for r in caplog.records)


def test_route_chain_is_identity_when_a_rule_raises():
    """End of the fail-open path: the chain comes back untouched."""
    chain = [_provider("gemini"), _provider("cerebras")]
    out = router.route_chain(
        chain, router.TaskDescriptor(agent_name="t"), rules=[_boom_rule]
    )
    assert out is chain


def test_call_with_failover_survives_a_raising_rule(monkeypatch):
    """Integration: a broken rule in the live _RULES must not fail the call —
    failover still serves it from the unrouted chain (ADR-012 §12)."""
    p1, p2 = _provider("first"), _provider("second")
    calls: list[str] = []

    async def ok(system, user, max_tokens):
        calls.append("first")
        return "answer from first"

    monkeypatch.setattr(p1, "call", ok)
    monkeypatch.setattr(providers, "_chain", [p1, p2])
    monkeypatch.setattr(router, "_RULES", [_boom_rule])

    result = asyncio.run(
        providers.call_with_failover("agent", "s", "u", max_tokens=100)
    )
    assert result == "answer from first"
    assert calls == ["first"]  # served normally, in the original chain order


# ---- route_chain(): the wired entry point --------------------------------


def test_route_chain_identity_with_default_rules():
    chain = [_provider("gemini"), _provider("cerebras")]
    out = router.route_chain(chain, router.TaskDescriptor(agent_name="t"))
    assert out is chain


def test_route_chain_applies_a_matching_rule():
    chain = [_provider("gemini"), _provider("ollama")]

    def local_first(_task):
        return router.RoutingDecision(preferred_families=("ollama",))

    out = router.route_chain(
        chain, router.TaskDescriptor(agent_name="t"), rules=[local_first]
    )
    assert [p.name for p in out] == ["ollama", "gemini"]


# ---- integration with call_with_failover ---------------------------------


def test_failover_unaffected_by_default_router(monkeypatch):
    """End-to-end: with the default empty ruleset, call_with_failover behaves
    exactly as before the router existed — first provider serves the call."""
    p1, p2 = _provider("first"), _provider("second")
    calls: list[str] = []

    async def ok(system, user, max_tokens):
        calls.append("first")
        return "answer from first"

    monkeypatch.setattr(p1, "call", ok)
    monkeypatch.setattr(providers, "_chain", [p1, p2])

    result = asyncio.run(
        providers.call_with_failover("agent", "s", "u", max_tokens=100)
    )
    assert result == "answer from first"
    assert calls == ["first"]


def test_router_reorders_the_live_chain(monkeypatch):
    """A registered rule actually changes which provider call_with_failover
    tries first — proving the seam is wired, not decorative."""
    preferred, other = _provider("ollama"), _provider("gemini")
    served: list[str] = []

    async def ollama_ok(system, user, max_tokens):
        served.append("ollama")
        return "local answer"

    async def gemini_ok(system, user, max_tokens):
        served.append("gemini")
        return "cloud answer"

    monkeypatch.setattr(preferred, "call", ollama_ok)
    monkeypatch.setattr(other, "call", gemini_ok)
    # Chain order is gemini-first; the rule must flip it to ollama-first.
    monkeypatch.setattr(providers, "_chain", [other, preferred])

    def local_first(_task):
        return router.RoutingDecision(
            preferred_families=("ollama",), rule_name="test-local-first"
        )

    monkeypatch.setattr(router, "_RULES", [local_first])

    result = asyncio.run(
        providers.call_with_failover("agent", "s", "u", max_tokens=100)
    )
    assert result == "local answer"
    assert served == ["ollama"]  # routed provider served it, gemini never called


def test_byok_bypasses_the_router(monkeypatch):
    """BYOK is a single premium target — a routing rule must not touch it."""
    served: list[str] = []

    def hijack(_task):  # would reorder if ever consulted on the BYOK path
        served.append("router-consulted")
        return router.RoutingDecision(preferred_families=("ollama",))

    monkeypatch.setattr(router, "_RULES", [hijack])
    monkeypatch.setattr(providers, "_chain", [_provider("free")])

    real_byok = providers.byok_provider

    def spy_byok(api_key: str) -> providers.Provider:
        p = real_byok(api_key)

        async def byok_ok(system, user, max_tokens):
            return "premium answer"

        object.__setattr__(p, "call", byok_ok)
        return p

    monkeypatch.setattr(providers, "byok_provider", spy_byok)
    result = asyncio.run(
        providers.call_with_failover(
            "agent", "s", "u", max_tokens=100, byok_key="sk-ant-user-key"
        )
    )
    assert result == "premium answer"
    assert served == []  # router never consulted on the BYOK path


# ---- Provider Router: vision (capability-driven, ADR-012 §6.3 P3) ---------

_IMG = "data:image/png;base64,AAAA"


def test_vision_rule_expresses_a_capability_not_a_family():
    """P3: the rule names the ``supports_vision`` capability — no family names."""
    decision = router._vision_rule(
        router.TaskDescriptor(agent_name="market-analyst", has_images=True)
    )
    assert decision is not None
    assert decision.prefer_flags == ("supports_vision",)
    assert decision.preferred_families == ()  # no embedded provider-family names
    assert decision.excluded_families == ()  # preference, never an exclusion
    assert decision.rule_name == "vision"


def test_vision_rule_ignores_a_text_only_call():
    """No images → no opinion, regardless of agent name (fail-open to chain)."""
    for agent in ("market-analyst", "report-writer", "anything"):
        assert router._vision_rule(router.TaskDescriptor(agent_name=agent)) is None, (
            agent
        )


def test_vision_reorders_by_registry_capability(monkeypatch):
    """Providers whose registered model supports vision float up — resolved from
    the registry via the model id, with no supports_vision attribute set."""
    cer = _provider("cerebras", model="gpt-oss-120b")  # registry: no vision
    gem = _provider("gemini", model="gemini-flash-latest")  # registry: vision
    out = router.apply_decision(
        [cer, gem],
        router.route(router.TaskDescriptor(agent_name="a", has_images=True)),
    )
    assert [p.name for p in out] == ["gemini", "cerebras"]


def test_vision_prefers_vision_capable_ollama_automatically():
    """A vision-capable local model (gemma3) is preferred; a text-only local
    model (qwen3) is not — driven entirely by the registry, no family list."""
    text_local = _provider("ollama", model="qwen3:4b")  # registry: no vision
    vision_local = _provider("gemma", model="gemma3:4b")  # registry: vision
    cer = _provider("cerebras", model="gpt-oss-120b")
    out = router.apply_decision(
        [cer, text_local, vision_local],
        router.route(router.TaskDescriptor(agent_name="a", has_images=True)),
    )
    # Only the vision-capable local model floats up; the text-only one stays put.
    assert out[0].name == "gemma"
    assert [p.name for p in out] == ["gemma", "cerebras", "ollama"]


def test_vision_falls_back_to_live_flag_for_unregistered_model():
    """An env-overridden (unregistered) model still routes by the live
    ``Provider.supports_vision`` flag — the fallback path."""
    cer = _provider("cerebras")  # unregistered, supports_vision=False
    gem = _provider("gemini", supports_vision=True)  # unregistered but flagged
    out = router.apply_decision(
        [cer, gem],
        router.route(router.TaskDescriptor(agent_name="a", has_images=True)),
    )
    assert [p.name for p in out] == ["gemini", "cerebras"]


def test_vision_is_graceful_when_no_provider_supports_it():
    """No vision-capable provider anywhere → chain unchanged (fail-open)."""
    chain = [_provider("cerebras"), _provider("openrouter")]
    out = router.apply_decision(
        chain,
        router.route(router.TaskDescriptor(agent_name="a", has_images=True)),
    )
    assert [p.name for p in out] == ["cerebras", "openrouter"]


def test_vision_failopen_when_an_earlier_rule_raises():
    """The vision rule still fires even if a preceding rule blows up."""
    decision = router.route(
        router.TaskDescriptor(agent_name="a", has_images=True),
        rules=[_boom_rule, router._vision_rule],
    )
    assert decision.rule_name == "vision"


def test_image_call_routes_vision_provider_to_the_front(monkeypatch):
    """End-to-end: an image call flips a cerebras-first chain to serve Gemini,
    so the image reaches a provider that can actually read it."""
    cer = _provider("cerebras", model="gpt-oss-120b")
    gem = _provider("gemini", model="gemini-flash-latest")
    served: list[str] = []

    async def gem_ok(system, user, max_tokens, images):
        served.append("gemini")
        return "gemini saw the image"

    async def cer_ok(system, user, max_tokens, images):
        served.append("cerebras")
        return "cerebras (text only)"

    monkeypatch.setattr(gem, "call", gem_ok)
    monkeypatch.setattr(cer, "call", cer_ok)
    monkeypatch.setattr(providers, "_chain", [cer, gem])  # cerebras first in chain

    result = asyncio.run(
        providers.call_with_failover(
            "market-analyst", "s", "u", max_tokens=100, images=[_IMG]
        )
    )
    assert result == "gemini saw the image"
    assert served == ["gemini"]  # routed to a vision provider; cerebras skipped


def test_image_call_falls_over_when_vision_provider_down(monkeypatch):
    """Requirement: if the preferred vision provider is unavailable, failover
    works exactly as today — Gemini is tried first, fails, cerebras serves."""
    cer = _provider("cerebras", model="gpt-oss-120b")
    gem = _provider("gemini", model="gemini-flash-latest")
    served: list[str] = []

    async def gem_fail(system, user, max_tokens, images):
        served.append("gemini-tried")
        raise RuntimeError("gemini down")

    async def cer_ok(system, user, max_tokens, images):
        served.append("cerebras")
        return "cerebras answer"

    monkeypatch.setattr(gem, "call", gem_fail)
    monkeypatch.setattr(cer, "call", cer_ok)
    monkeypatch.setattr(providers, "_chain", [cer, gem])

    result = asyncio.run(
        providers.call_with_failover(
            "market-analyst", "s", "u", max_tokens=100, images=[_IMG]
        )
    )
    assert result == "cerebras answer"
    # Gemini was routed to the front and attempted first, then failover took over.
    assert served == ["gemini-tried", "cerebras"]


def test_text_only_call_keeps_original_chain_order(monkeypatch):
    """Backward compatibility: a normal (no-image) consulting call is untouched —
    the chain keeps its original order and the first provider serves it."""
    cer, gem = _provider("cerebras"), _provider("gemini")
    served: list[str] = []

    async def cer_ok(system, user, max_tokens):
        served.append("cerebras")
        return "answer"

    monkeypatch.setattr(cer, "call", cer_ok)
    monkeypatch.setattr(providers, "_chain", [cer, gem])  # cerebras first

    result = asyncio.run(
        providers.call_with_failover("financial-analyst", "s", "u", max_tokens=100)
    )
    assert result == "answer"
    assert served == ["cerebras"]  # order untouched, no reordering


# ---- Provider Router: long-context (capability-driven, ADR-012 §6.3) ------


def test_long_context_rule_ignores_small_prompts():
    for size in (None, 0, 100, router._LONG_CONTEXT_THRESHOLD - 1):
        assert (
            router._long_context_rule(
                router.TaskDescriptor(agent_name="a", prompt_size=size)
            )
            is None
        ), size


def test_long_context_rule_fires_above_threshold():
    decision = router._long_context_rule(
        router.TaskDescriptor(agent_name="a", prompt_size=10000)
    )
    assert decision is not None
    assert decision.min_context == 10000
    assert decision.rule_name == "long-context"


def test_long_context_deprioritizes_tier_capped_provider():
    """A large prompt prefers a big-window provider over a tier-capped one:
    GitHub's usable context is 8k (registry max_request_tokens), Gemini's ~1M."""
    gh = _provider("github", model="openai/gpt-4.1-mini")  # effective 8192
    gem = _provider("gemini", model="gemini-flash-latest")  # 1M
    out = router.apply_decision(
        [gh, gem],
        router.route(router.TaskDescriptor(agent_name="a", prompt_size=20000)),
    )
    assert [p.name for p in out] == ["gemini", "github"]  # big-window first


def test_long_context_is_graceful_when_no_provider_fits():
    """If nothing can hold the prompt, order is unchanged (fail-open) — failover
    still tries everything rather than the call being stranded."""
    gh = _provider("github", model="openai/gpt-4.1-mini")  # 8192
    out = router.apply_decision(
        [gh],
        router.route(router.TaskDescriptor(agent_name="a", prompt_size=50000)),
    )
    assert [p.name for p in out] == ["github"]


# ---- Provider Router: structured JSON (capability-driven, ADR-012 §6.3) ---


def test_json_rule_requires_the_needs_json_signal():
    assert router._json_rule(router.TaskDescriptor(agent_name="a")) is None
    decision = router._json_rule(router.TaskDescriptor(agent_name="a", needs_json=True))
    assert decision is not None
    assert decision.prefer_flags == ("supports_json",)
    assert decision.rule_name == "structured-json"


def test_json_prefers_json_capable_provider():
    """Cerebras' model supports JSON (registry); Cloudflare's is marked not to."""
    cf = _provider("cloudflare", model="@cf/meta/llama-3.3-70b-instruct-fp8-fast")
    cer = _provider("cerebras", model="gpt-oss-120b")
    out = router.apply_decision(
        [cf, cer],
        router.route(router.TaskDescriptor(agent_name="a", needs_json=True)),
    )
    assert [p.name for p in out] == ["cerebras", "cloudflare"]


def test_first_match_wins_vision_over_long_context():
    """Rules are a priority list: an image call that is ALSO large gets the
    vision decision (first match), not long-context."""
    decision = router.route(
        router.TaskDescriptor(agent_name="a", has_images=True, prompt_size=99999)
    )
    assert decision.rule_name == "vision"


# ---- Provider Router: routing telemetry (ADR-012 §12, observability) ------


def test_telemetry_logs_an_applied_decision(caplog):
    cer = _provider("cerebras", model="gpt-oss-120b")
    gem = _provider("gemini", model="gemini-flash-latest")
    task = router.TaskDescriptor(agent_name="market-analyst", has_images=True)
    with caplog.at_level("DEBUG", logger="app.pipeline.router"):
        router.route_chain([cer, gem], task)
    line = next(r.getMessage() for r in caplog.records if "matched=" in r.getMessage())
    assert "matched=vision" in line
    assert "status=applied" in line
    assert "selected=['gemini', 'cerebras']" in line
    assert "reason=" in line


def test_telemetry_logs_unrouted_for_a_no_opinion_decision(caplog):
    with caplog.at_level("DEBUG", logger="app.pipeline.router"):
        router.route_chain(
            [_provider("cerebras")], router.TaskDescriptor(agent_name="reviewer")
        )
    line = next(r.getMessage() for r in caplog.records if "matched=" in r.getMessage())
    assert "matched=none" in line
    assert "status=unrouted" in line


def test_telemetry_logs_fell_open_when_no_provider_satisfies(caplog):
    """A rule matched (image call) but no provider is vision-capable → the chain
    is unchanged and the telemetry records the fail-open path explicitly."""
    chain = [_provider("cerebras"), _provider("openrouter")]
    with caplog.at_level("DEBUG", logger="app.pipeline.router"):
        router.route_chain(
            chain, router.TaskDescriptor(agent_name="a", has_images=True)
        )
    line = next(r.getMessage() for r in caplog.records if "matched=" in r.getMessage())
    assert "matched=vision" in line
    assert "status=fell-open" in line
