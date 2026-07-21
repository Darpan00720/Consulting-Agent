"""Tests for the Workflow Router (ADR-013 W1, finalized in W1.1).

The router is a pure function: classify a unit of work and select its owning
target. It never dispatches, never calls ``invoke``, and never raises. These
tests cover every category, the consulting-domain guardrail (independent of the
classifier, hints, and precedence), fail-open behavior, robust matching,
telemetry, malformed/failing targets, and depth-cap ownership.

Tests use a local ``FakeTarget`` double rather than the router's private
adapter, so they depend only on the public ``Target`` protocol.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.workflow import router, targets
from app.workflow.router import RoutingContext, Work, route
from app.workflow.targets import WorkflowCategory as C


def _ctx() -> RoutingContext:
    return RoutingContext(trace_id="t-1")


@dataclass
class FakeTarget:
    """A local test double implementing the public Target protocol only."""

    name: str
    categories: tuple[C, ...]
    is_available: bool = True
    raise_on_can_handle: bool = False
    raise_on_available: bool = False

    def describe(self) -> targets.TargetInfo:
        return targets.TargetInfo(
            name=self.name, kind="test", categories=self.categories
        )

    def can_handle(self, category: C) -> bool:
        if self.raise_on_can_handle:
            raise RuntimeError("can_handle boom")
        return category in self.categories

    def available(self) -> bool:
        if self.raise_on_available:
            raise RuntimeError("available boom")
        return self.is_available


def _engineering_registry(**overrides) -> dict[str, object]:
    """A registry of local fakes mirroring the default roster; overridable."""
    reg: dict[str, object] = {
        "claude": FakeTarget(
            "claude",
            (
                C.CODING,
                C.DEBUGGING,
                C.CODE_REVIEW,
                C.DOCUMENTATION,
                C.REPOSITORY_ANALYSIS,
                C.RESEARCH,
                C.GENERAL_REASONING,
            ),
        ),
        "codex": FakeTarget(
            "codex", (C.CODING, C.DEBUGGING, C.CODE_REVIEW, C.DOCUMENTATION)
        ),
        "consulting": FakeTarget("consulting", (C.BUSINESS_CONSULTING,)),
        "repository_analysis": FakeTarget(
            "repository_analysis", (C.REPOSITORY_ANALYSIS,)
        ),
    }
    reg.update(overrides)
    return reg


# ---- Target interface (ADR-013 §4a) --------------------------------------


def test_targets_implement_the_full_interface():
    """W2: invoke() now exists (added for the Dispatcher, tested in
    test_dispatcher.py) — but the Workflow Router itself still never calls it;
    that boundary is tested separately (router only reads describe/can_handle/
    available)."""
    for t in targets.default_registry().values():
        assert isinstance(t, targets.Target)
        assert hasattr(t, "invoke")
        assert asyncio.iscoroutinefunction(t.invoke)


def test_graphify_is_a_tool_not_a_target():
    reg = targets.default_registry()
    assert "graphify" not in reg
    assert "graphify" in reg["repository_analysis"].describe().tools


def test_can_handle_and_available():
    codex = targets.codex_target()
    assert codex.can_handle(C.CODING) is True
    assert codex.can_handle(C.BUSINESS_CONSULTING) is False
    assert targets.codex_target(available=False).available() is False


# ---- Classification: categories via explicit signals ---------------------


def test_classify_coding_from_intent():
    assert router.classify(Work(text="please refactor this module"))[0] is C.CODING


def test_classify_debugging_from_command():
    cat, reason = router.classify(Work(command="/codex:rescue"))
    assert cat is C.DEBUGGING and "command" in reason


def test_classify_code_review_from_command():
    assert router.classify(Work(command="/codex:review"))[0] is C.CODE_REVIEW


def test_classify_documentation_from_files():
    cat, reason = router.classify(Work(files=("docs/ADR-014.md", "README.md")))
    assert cat is C.DOCUMENTATION and "file types" in reason


def test_classify_repository_analysis_from_intent():
    assert (
        router.classify(Work(text="show me the dependency graph"))[0]
        is C.REPOSITORY_ANALYSIS
    )


def test_classify_research_from_intent():
    assert (
        router.classify(Work(text="please investigate the latest options"))[0]
        is C.RESEARCH
    )


def test_classify_general_reasoning_default():
    cat, reason = router.classify(Work(text="what's a good name for a cat?"))
    assert cat is C.GENERAL_REASONING and "default" in reason


def test_category_hint_overrides_within_classify():
    cat, reason = router.classify(
        Work(text="refactor this", category_hint="documentation")
    )
    assert cat is C.DOCUMENTATION and "hint" in reason


def test_unknown_category_hint_falls_through():
    assert (
        router.classify(Work(text="refactor this", category_hint="nonsense"))[0]
        is C.CODING
    )


# ---- A. Consulting-domain guardrail (runs first, independent) -------------


def test_consulting_detected_from_domain_phrases():
    """The review's false-negative set must now be caught by the domain detector."""
    for phrase in (
        "help with our pricing strategy",
        "evaluate this m&a opportunity",
        "a turnaround plan for the division",
        "improve profitability across the unit",
        "run due diligence on the target",
        "a restructuring of the org",
        "our market entry into Brazil",
    ):
        hit, _ = router.is_consulting_domain(Work(text=phrase))
        assert hit is True, phrase


def test_consulting_false_negative_now_routes_to_governed_agent():
    decision = route(Work(text="advise on our pricing strategy"), _ctx())
    assert decision.category is C.BUSINESS_CONSULTING
    assert decision.selected_target == "consulting"


def test_category_hint_cannot_override_consulting_governance():
    """A conflicting engineering hint must NOT pull consulting work to a dev tool."""
    decision = route(
        Work(text="evaluate this m&a opportunity", category_hint="coding"), _ctx()
    )
    assert decision.category is C.BUSINESS_CONSULTING
    assert decision.selected_target == "consulting"  # NOT codex


def test_consulting_detected_from_skill_and_agent():
    assert router.is_consulting_domain(Work(skill="solve-case"))[0] is True
    assert router.is_consulting_domain(Work(agent="financial-analyst"))[0] is True


def test_consulting_routes_to_governed_agent():
    decision = route(Work(skill="solve-case"), _ctx())
    assert decision.category is C.BUSINESS_CONSULTING
    assert decision.selected_target == "consulting"


def test_consulting_hard_blocks_when_governed_agent_unavailable():
    reg = _engineering_registry(
        consulting=FakeTarget(
            "consulting", (C.BUSINESS_CONSULTING,), is_available=False
        )
    )
    decision = route(Work(skill="solve-case"), _ctx(), registry=reg)
    assert decision.selected_target is None
    assert "governed agent" in decision.guardrail_verdict


def test_guardrail_is_independent_of_target_registration():
    """A rogue target that CLAIMS consulting is never selected — the allow-list
    restricts regardless of can_handle (ADR-013 §8)."""
    reg = _engineering_registry()
    del reg["consulting"]
    reg["rogue"] = FakeTarget("rogue", (C.BUSINESS_CONSULTING,))
    decision = route(Work(skill="solve-case"), _ctx(), registry=reg)
    assert decision.selected_target is None  # rogue not allow-listed → hard block


# ---- Ambiguity & robust matching (item D) --------------------------------


def test_ambiguous_request_resolves_by_fixed_priority():
    cat, reason = router.classify(Work(text="review this code and refactor it"))
    assert cat is C.CODE_REVIEW
    assert "over" in reason  # losing category (coding) recorded


def test_undocumented_does_not_match_documentation():
    decision = route(Work(text="there is an undocumented bug somewhere"), _ctx())
    assert decision.category is not C.DOCUMENTATION


def test_negated_keyword_is_not_matched():
    decision = route(
        Work(text="do not research the competitors, just build it"), _ctx()
    )
    assert decision.category is not C.RESEARCH


def test_unknown_request_is_general_reasoning():
    decision = route(Work(text="hello there"), _ctx())
    assert decision.category is C.GENERAL_REASONING
    assert decision.selected_target == "claude"


# ---- Selection & pass-through --------------------------------------------


def test_coding_selects_codex_then_claude():
    decision = route(Work(text="implement a parser"), _ctx())
    assert decision.selected_target == "codex"
    assert decision.fallback_targets == ("claude",)
    assert decision.fallback_used is False


def test_documentation_selects_claude_primary():
    decision = route(Work(files=("README.md",)), _ctx())
    assert decision.selected_target == "claude"


def test_repository_analysis_selects_its_agent_then_claude():
    decision = route(Work(text="analyze the repo structure"), _ctx())
    assert decision.category is C.REPOSITORY_ANALYSIS
    assert decision.selected_target == "repository_analysis"


def test_explicit_command_pass_through():
    decision = route(Work(command="/codex:review"), _ctx())
    assert decision.category is C.CODE_REVIEW
    assert decision.selected_target == "codex"
    assert decision.guardrail_verdict == "ok"


def test_idempotent_re_entry_is_not_reclassified():
    ctx = RoutingContext(trace_id="t", category=C.CODING, classified=True)
    decision = route(Work(text="write a readme and document everything"), ctx)
    assert decision.category is C.CODING
    assert "idempotent" in decision.reason


# ---- Unavailable / malformed targets (fail-open at target level) ---------


def test_unavailable_primary_falls_to_secondary_and_flags_fallback():
    reg = _engineering_registry(
        codex=FakeTarget("codex", (C.CODING,), is_available=False)
    )
    decision = route(Work(text="implement a parser"), _ctx(), registry=reg)
    assert decision.selected_target == "claude"
    assert decision.fallback_used is True


def test_all_targets_unavailable_blocks_without_crashing():
    reg = {
        "claude": FakeTarget(
            "claude", (C.GENERAL_REASONING, C.CODING), is_available=False
        ),
        "codex": FakeTarget("codex", (C.CODING,), is_available=False),
    }
    decision = route(Work(text="implement a parser"), _ctx(), registry=reg)
    assert decision.selected_target is None
    assert decision.guardrail_verdict.startswith("blocked")


def test_malformed_target_can_handle_is_skipped_not_fatal():
    reg = _engineering_registry(
        codex=FakeTarget("codex", (C.CODING,), raise_on_can_handle=True)
    )
    decision = route(Work(text="implement a parser"), _ctx(), registry=reg)
    assert decision.selected_target == "claude"  # broken codex skipped, not crashed


def test_target_availability_probe_failure_is_treated_as_unavailable():
    reg = _engineering_registry(
        codex=FakeTarget("codex", (C.CODING,), raise_on_available=True)
    )
    decision = route(Work(text="implement a parser"), _ctx(), registry=reg)
    assert decision.selected_target == "claude"
    assert decision.fallback_used is True


# ---- B. Fail-open behavior (ADR-013 §7) ----------------------------------


def test_classifier_exception_fails_open_to_general(monkeypatch):
    def boom(_work):
        raise RuntimeError("classifier exploded")

    monkeypatch.setattr(router, "classify", boom)
    decision = route(Work(text="hello there"), _ctx())
    assert decision.category is C.GENERAL_REASONING
    assert decision.selected_target == "claude"
    assert decision.fallback_used is True
    assert "classifier exploded" in decision.failure_reason


def test_selection_exception_still_hard_blocks_consulting(monkeypatch):
    """Even a routing failure must not leak consulting work to a dev tool."""

    def boom(_category, _registry):
        raise RuntimeError("selection exploded")

    monkeypatch.setattr(router, "_select", boom)
    decision = route(Work(skill="solve-case"), _ctx())
    assert decision.category is C.BUSINESS_CONSULTING
    assert decision.selected_target is None  # blocked, not failed open to Claude
    assert decision.failure_reason is not None


def test_route_never_raises_on_arbitrary_target_failure():
    reg = {
        "claude": FakeTarget("claude", (C.GENERAL_REASONING,), raise_on_can_handle=True)
    }
    decision = route(Work(text="hi"), _ctx(), registry=reg)  # must not raise
    assert isinstance(decision, router.WorkflowDecision)


# ---- E. Telemetry ---------------------------------------------------------


def test_decision_exposes_telemetry_metadata():
    decision = route(Work(text="implement a parser"), _ctx())
    assert decision.routing_context.trace_id == "t-1"
    assert decision.fallback_used is False
    assert decision.failure_reason is None


def test_log_includes_trace_fallback_and_failure_fields(caplog):
    with caplog.at_level("DEBUG", logger="app.workflow.router"):
        route(Work(command="/codex:review"), _ctx())
    line = next(
        r.getMessage() for r in caplog.records if "workflow-route" in r.getMessage()
    )
    assert "trace_id=t-1" in line
    assert "category=code_review" in line
    assert "target=codex" in line
    assert "fallback_used=" in line
    assert "failure_reason=" in line


def test_context_is_stamped_classified_and_category():
    decision = route(Work(text="implement a parser"), _ctx())
    assert decision.routing_context.classified is True
    assert decision.routing_context.category is C.CODING
    assert decision.routing_context.trace_id == "t-1"


# ---- C. dispatch_depth: router validates, host enforces ------------------


def test_exceeds_dispatch_cap_is_a_pure_validation_helper():
    assert (
        router.exceeds_dispatch_cap(RoutingContext(trace_id="t", dispatch_depth=0))
        is False
    )
    assert (
        router.exceeds_dispatch_cap(
            RoutingContext(trace_id="t", dispatch_depth=router.MAX_DISPATCH_DEPTH + 1)
        )
        is True
    )


def test_router_does_not_enforce_depth_cap():
    """The router is pure — a deep context still routes normally; enforcement is
    the host's job (ADR-013 §6a), not the router's."""
    deep = RoutingContext(trace_id="t", dispatch_depth=999)
    decision = route(Work(text="implement a parser"), deep)
    assert decision.selected_target == "codex"  # routed, not refused
