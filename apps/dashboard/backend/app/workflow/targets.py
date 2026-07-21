"""Workflow Router targets and the `Target` interface (ADR-013 §4a).

A **Target** is an agent/toolchain that can OWN a unit of work. The Workflow
Router (W1) only SELECTS a target — it reads ``can_handle`` / ``available`` /
``describe``. The Dispatcher (W2) is the only caller of ``invoke`` — dispatch is
the host's job (ADR-013 §2a, Option A); the router never calls it.

Graphify is intentionally NOT a target (ADR-013 §4a, F4). Repository analysis is
owned by an agent target (`repository_analysis`) that *uses* Graphify as a tool,
declared in its ``describe().tools`` — never selected on its own.

**``invoke()`` scope (W2, deliberate boundary):** ``ClaudeSessionTarget`` is
wired to the REAL Provider Router (``providers.call_with_failover``, ADR-012)
— this backend process genuinely can execute that call. Codex, the consulting
skill, and Graphify are external CLI/skill/MCP surfaces this Python backend
does not own; having generic dispatch code shell out to a real Codex process or
spend real API/consulting-pipeline resources as a side effect of routing is a
live-integration decision beyond "build the execution layer," so those three
ship as deterministic, side-effect-free placeholder adapters behind an
injectable ``runner`` hook — the same pattern already used for W1's
``available()`` flag. Real wiring plugs into ``runner`` later without touching
the Dispatcher.

**W3 update — platform standardization, no behavioral change (ADR-013 W3
requirement 12):** every ``invoke()`` DEFAULT path now delegates to
``AgentRuntime.execute()`` against the matching built-in ``app.agents.builtin``
agent, rather than hand-rolling its logic inline. Output content, success/error
semantics, and the ``runner`` override escape hatch are byte-identical to W2 —
only the wrapper changed (timing/telemetry/retries/error-mapping now live once,
in the platform, not duplicated per Target). A caller-supplied ``runner``
still bypasses the Agent Platform entirely, exactly as in W2, for tests and
future ad-hoc wiring that don't need the full platform.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from app.workflow.router import RoutingContext, Work


class WorkflowCategory(StrEnum):
    """The task-types the Workflow Router classifies into (ADR-013 §3)."""

    CODING = "coding"
    DEBUGGING = "debugging"
    CODE_REVIEW = "code_review"
    DOCUMENTATION = "documentation"
    REPOSITORY_ANALYSIS = "repository_analysis"
    RESEARCH = "research"
    BUSINESS_CONSULTING = "business_consulting"
    GENERAL_REASONING = "general_reasoning"


@dataclass(frozen=True)
class TargetInfo:
    """Static metadata a target advertises (ADR-013 §4a ``describe``)."""

    name: str
    kind: str  # "session" | "cli" | "skill" | "agent"
    categories: tuple[WorkflowCategory, ...]
    tools: tuple[str, ...] = ()  # tools the target USES, e.g. ("graphify",)


@dataclass(frozen=True)
class InvokeResult:
    """What ``invoke()`` returns — the Target's outcome for one unit of work.

    Part of the Target contract's return shape, so it lives beside ``Target``
    rather than in the dispatcher. ``invoke`` itself never raises for an
    ordinary failure — it reports one here; the Dispatcher still guards the
    call defensively (ADR-013 §7 discipline extended to W2).
    """

    success: bool
    output: str | None = None
    error: str | None = None


@runtime_checkable
class Target(Protocol):
    """The minimum contract every selectable target satisfies (ADR-013 §4a).

    ``invoke`` is called ONLY by the Dispatcher (W2) — the Workflow Router
    never calls it (ADR-013 §2a).
    """

    def describe(self) -> TargetInfo: ...
    def can_handle(self, category: WorkflowCategory) -> bool: ...
    def available(self) -> bool: ...
    async def invoke(self, work: Work, context: RoutingContext) -> InvokeResult: ...


InvokeFn = Callable[["Work", "RoutingContext"], Awaitable[InvokeResult]]


# ---- The initial target roster (ADR-013 §4) ------------------------------

_C = WorkflowCategory


@dataclass
class ClaudeSessionTarget:
    """Primary, always-available session agent; owns general reasoning and every
    engineering category. Deliberately does NOT claim business consulting — that
    is product-governed work (ADR-010 §6c), reinforced by the guardrail.

    ``invoke`` is REAL: it calls ``providers.call_with_failover`` (ADR-012),
    the one target this backend can genuinely execute end-to-end. The
    ``agent_name`` embeds ``context.trace_id`` so Provider Router telemetry
    correlates with Workflow Router telemetry without a shared global or a new
    id (W2 §7 "no duplicated IDs").
    """

    is_available: bool = True

    def describe(self) -> TargetInfo:
        return TargetInfo(
            name="claude",
            kind="session",
            categories=(
                _C.CODING,
                _C.DEBUGGING,
                _C.CODE_REVIEW,
                _C.DOCUMENTATION,
                _C.REPOSITORY_ANALYSIS,
                _C.RESEARCH,
                _C.GENERAL_REASONING,
            ),
        )

    def can_handle(self, category: WorkflowCategory) -> bool:
        return category in self.describe().categories

    def available(self) -> bool:
        return self.is_available

    async def invoke(self, work: Work, context: RoutingContext) -> InvokeResult:
        # Lazy: keep app.workflow importable standalone, and avoid a top-level
        # dependency on app.agents (the Agent Platform is the lower layer;
        # this Target is one of its callers, not the reverse — ADR-013 W3).
        from app.agents import builtin as agent_builtin
        from app.agents.runtime import default_runtime

        result = await default_runtime().execute(
            agent_builtin.claude_agent(available=self.is_available), work, context
        )
        return InvokeResult(
            success=result.success, output=result.output, error=result.error
        )


@dataclass
class CodexTarget:
    """Independent CLI model for mechanical code work + adversarial review.

    Placeholder ``invoke`` (module docstring) — override via ``runner`` for
    real CLI wiring.
    """

    is_available: bool = True
    runner: InvokeFn | None = None

    def describe(self) -> TargetInfo:
        return TargetInfo(
            name="codex",
            kind="cli",
            categories=(_C.CODING, _C.DEBUGGING, _C.CODE_REVIEW, _C.DOCUMENTATION),
        )

    def can_handle(self, category: WorkflowCategory) -> bool:
        return category in self.describe().categories

    def available(self) -> bool:
        return self.is_available

    async def invoke(self, work: Work, context: RoutingContext) -> InvokeResult:
        if self.runner is not None:
            try:
                return await self.runner(work, context)
            except Exception as exc:  # noqa: BLE001 — invoke reports, never raises
                return InvokeResult(success=False, error=f"{type(exc).__name__}: {exc}")
        from app.agents import builtin as agent_builtin
        from app.agents.runtime import default_runtime

        result = await default_runtime().execute(
            agent_builtin.codex_agent(available=self.is_available), work, context
        )
        return InvokeResult(
            success=result.success, output=result.output, error=result.error
        )


@dataclass
class ConsultingSkillTarget:
    """The governed StratAgent `solve-case` pipeline — the ONLY target allowed to
    own business consulting (guardrail allow-list, ADR-013 §6.4/§8).

    Placeholder ``invoke`` (module docstring) — override via ``runner`` for
    real skill wiring.
    """

    is_available: bool = True
    runner: InvokeFn | None = None

    def describe(self) -> TargetInfo:
        return TargetInfo(
            name="consulting", kind="skill", categories=(_C.BUSINESS_CONSULTING,)
        )

    def can_handle(self, category: WorkflowCategory) -> bool:
        return category in self.describe().categories

    def available(self) -> bool:
        return self.is_available

    async def invoke(self, work: Work, context: RoutingContext) -> InvokeResult:
        if self.runner is not None:
            try:
                return await self.runner(work, context)
            except Exception as exc:  # noqa: BLE001 — invoke reports, never raises
                return InvokeResult(success=False, error=f"{type(exc).__name__}: {exc}")
        from app.agents import builtin as agent_builtin
        from app.agents.runtime import default_runtime

        result = await default_runtime().execute(
            agent_builtin.consulting_agent(available=self.is_available), work, context
        )
        return InvokeResult(
            success=result.success, output=result.output, error=result.error
        )


@dataclass
class RepositoryAnalysisTarget:
    """An agent that answers structural questions USING Graphify's graph tools.
    Graphify is a tool it holds (``tools``), not a target of its own (F4).

    Placeholder ``invoke`` (module docstring) — override via ``runner`` for
    real Graphify MCP wiring.
    """

    is_available: bool = True
    runner: InvokeFn | None = None

    def describe(self) -> TargetInfo:
        return TargetInfo(
            name="repository_analysis",
            kind="agent",
            categories=(_C.REPOSITORY_ANALYSIS,),
            tools=("graphify",),
        )

    def can_handle(self, category: WorkflowCategory) -> bool:
        return category in self.describe().categories

    def available(self) -> bool:
        return self.is_available

    async def invoke(self, work: Work, context: RoutingContext) -> InvokeResult:
        if self.runner is not None:
            try:
                return await self.runner(work, context)
            except Exception as exc:  # noqa: BLE001 — invoke reports, never raises
                return InvokeResult(success=False, error=f"{type(exc).__name__}: {exc}")
        from app.agents import builtin as agent_builtin
        from app.agents.runtime import default_runtime

        result = await default_runtime().execute(
            agent_builtin.repository_analysis_agent(available=self.is_available),
            work,
            context,
        )
        return InvokeResult(
            success=result.success, output=result.output, error=result.error
        )


def claude_target(available: bool = True) -> ClaudeSessionTarget:
    return ClaudeSessionTarget(is_available=available)


def codex_target(available: bool = True, runner: InvokeFn | None = None) -> CodexTarget:
    return CodexTarget(is_available=available, runner=runner)


def consulting_target(
    available: bool = True, runner: InvokeFn | None = None
) -> ConsultingSkillTarget:
    return ConsultingSkillTarget(is_available=available, runner=runner)


def repository_analysis_target(
    available: bool = True, runner: InvokeFn | None = None
) -> RepositoryAnalysisTarget:
    return RepositoryAnalysisTarget(is_available=available, runner=runner)


def default_registry() -> dict[str, Target]:
    """The target registry, keyed by name. Callers/tests may pass their own to
    ``router.route``/``dispatcher.dispatch`` (the same injection pattern the
    Provider Router uses)."""
    roster = (
        claude_target(),
        codex_target(),
        consulting_target(),
        repository_analysis_target(),
    )
    return {t.describe().name: t for t in roster}
