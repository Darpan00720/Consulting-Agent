"""Host / Dispatcher (ADR-013 §2a) — executes a WorkflowDecision.

This is the concrete implementation of "the host owns dispatch": the Workflow
Router (``router.py``) emits a pure ``WorkflowDecision`` and never calls
``invoke``; THIS module is the thing that reads that decision and actually
calls ``Target.invoke(...)``, walking the fallback chain, honoring guardrails,
enforcing the dispatch-depth cap, and producing a deterministic result. Any
real host (a Claude Flow hook, a CLI, an API handler) is expected to call
``dispatch()`` rather than reimplement this logic — ADR-013's "Claude Flow
remains the dispatcher" is realized by Claude Flow (or any host) invoking this
function, not by duplicating its mechanics.

**Guardrails are never re-derived here.** The Dispatcher only ever attempts
``decision.selected_target`` followed by ``decision.fallback_targets`` — both
already guardrail-filtered by the router's ``_select`` (ADR-013 §8, F8). A
rogue or newly-registered target can never be reached through dispatch unless
the router already decided it belongs in that list. This is the concrete
"never bypass guardrails" guarantee (requirement 4): enforced by construction,
not by a second guardrail check.

**Never crashes (requirement 8).** Every step — the decision itself,
availability, ``invoke`` — is guarded. A malformed target, a raised exception,
a timeout, or a cancellation all resolve to a valid ``DispatcherResult``.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, replace
from enum import StrEnum

from app.workflow.router import (
    MAX_DISPATCH_DEPTH,
    RoutingContext,
    Work,
    WorkflowDecision,
    exceeds_dispatch_cap,
)
from app.workflow.targets import InvokeResult, Target

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT_S = 30.0


# ---- Lifecycle state machine (requirement 3) ------------------------------


class DispatchState(StrEnum):
    """Explicit dispatch lifecycle states.

    Transitions (documented per-edge — every one below is reachable and is
    exercised by a test in ``tests/test_dispatcher.py``):

    ``PENDING → VALIDATED``
        Always, on entry — the decision object itself is well-formed.
    ``VALIDATED → BLOCKED``
        ``decision.selected_target is None`` (a guardrail block, or the router
        found no available target). Terminal. **No fallback is attempted** —
        the router's own ``fallback_targets`` is already empty in this case
        (its guardrail-filtered candidate list was exhausted), and a blocked
        decision is a stop, not a retry.
    ``VALIDATED → FAILED``
        The dispatch-depth cap (``exceeds_dispatch_cap``) is already exceeded
        for this nested unit. Terminal, before any target is touched —
        recursion is refused deterministically, never attempted.
    ``VALIDATED → PRIMARY``
        Depth is within budget; begin attempting ``selected_target``.
    ``PRIMARY → COMPLETED``
        The primary target's ``invoke`` returns ``success=True`` within its
        timeout. Terminal.
    ``PRIMARY → FALLBACK``
        The primary is unavailable, raises, returns ``success=False``, or
        times out, AND at least one fallback target remains.
    ``PRIMARY → FAILED``
        The primary fails AND there are no fallback targets. Terminal.
    ``FALLBACK → COMPLETED``
        Any fallback candidate's ``invoke`` succeeds. Terminal.
    ``FALLBACK → FALLBACK``
        A fallback candidate fails and a further fallback remains — the state
        stays ``FALLBACK`` across multiple attempts (the diagram's single
        "fallback" box is repeated once per remaining candidate).
    ``FALLBACK → FAILED``
        Every candidate (primary + all fallbacks) has failed. Terminal.
    ``(any) → FAILED`` (cancelled=True)
        A ``CancellationToken`` is signaled mid-dispatch. Terminal; nothing
        left running (requirement 10 — no orphan execution).
    """

    PENDING = "pending"
    VALIDATED = "validated"
    PRIMARY = "primary"
    FALLBACK = "fallback"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


_TERMINAL = frozenset(
    {DispatchState.COMPLETED, DispatchState.FAILED, DispatchState.BLOCKED}
)


@dataclass(frozen=True)
class Transition:
    """One state-machine edge, for the auditable transition log (requirement 3:
    "Document every transition" — documented in code above AND recorded in
    every result, not just described in a docstring)."""

    from_state: DispatchState
    to_state: DispatchState
    note: str


@dataclass(frozen=True)
class DispatchAttempt:
    """One target's outcome within a dispatch (requirement 4/8)."""

    target: str
    role: DispatchState  # PRIMARY or FALLBACK
    success: bool
    error: str | None = None
    duration_ms: float = 0.0


@dataclass(frozen=True)
class DispatcherResult:
    """The Dispatcher's deterministic output (requirement 8) — always produced,
    never an exception. Telemetry fields (requirement 7) are first-class, not
    log-only: ``trace_id`` (reused, never duplicated — ADR-012 correlation),
    ``category``, ``target_used``, the transition log, ``duration_ms``,
    ``fallback_count``, ``failure_reason``, and ``final_state`` as the
    completion status.
    """

    trace_id: str
    category: str
    final_state: DispatchState
    target_used: str | None
    output: str | None
    attempts: tuple[DispatchAttempt, ...]
    transitions: tuple[Transition, ...]
    fallback_count: int
    duration_ms: float
    failure_reason: str | None
    cancelled: bool
    routing_context: RoutingContext

    @property
    def success(self) -> bool:
        return self.final_state is DispatchState.COMPLETED


# ---- Cancellation (requirement 10) ----------------------------------------


class CancellationToken:
    """A cooperative cancellation signal, passed explicitly — never a global.

    Backed by an ``asyncio.Event`` so the dispatch loop can race an in-flight
    ``invoke`` against cancellation (see ``_run_one``) rather than only
    checking between attempts.
    """

    def __init__(self) -> None:
        self._event = asyncio.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        await self._event.wait()


# ---- Guarded target inspection (defense in depth beyond the router's) -----


def _safe_available(target: Target) -> tuple[bool, str | None]:
    try:
        return bool(target.available()), None
    except Exception as exc:  # noqa: BLE001 — a malformed target is skipped
        return False, f"{type(exc).__name__}: {exc}"


async def _run_one(
    target: Target,
    work: Work,
    context: RoutingContext,
    timeout_s: float,
    token: CancellationToken,
) -> tuple[InvokeResult | None, str | None, bool]:
    """Run one target's ``invoke`` under a timeout, racing cancellation.

    Returns ``(result, error, cancelled)`` — exactly one of ``result`` or
    ``error`` is set unless cancelled, in which case both are ``None``.
    Guarantees no orphan task: the loser of the race is always cancelled and
    awaited before returning (requirement 10 — "no leaked state").
    """
    invoke_task: asyncio.Task[InvokeResult] = asyncio.ensure_future(
        target.invoke(work, context)
    )
    cancel_task: asyncio.Task[None] = asyncio.ensure_future(token.wait())
    done, _pending = await asyncio.wait(
        {invoke_task, cancel_task},
        timeout=timeout_s,
        return_when=asyncio.FIRST_COMPLETED,
    )

    if cancel_task in done:
        invoke_task.cancel()
        await asyncio.gather(invoke_task, return_exceptions=True)
        return None, None, True

    if invoke_task not in done:
        # Timed out. Cancel + await the loser; cancel the still-pending watcher.
        invoke_task.cancel()
        await asyncio.gather(invoke_task, return_exceptions=True)
        cancel_task.cancel()
        await asyncio.gather(cancel_task, return_exceptions=True)
        return None, f"timeout after {timeout_s}s", False

    cancel_task.cancel()
    await asyncio.gather(cancel_task, return_exceptions=True)
    try:
        result = invoke_task.result()
    except Exception as exc:  # noqa: BLE001 — invoke() raised despite its own guard
        return None, f"{type(exc).__name__}: {exc}", False
    return result, None, False


# ---- dispatch(): the entry point -------------------------------------------


async def dispatch(
    decision: WorkflowDecision,
    registry: dict[str, Target],
    work: Work,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    target_timeouts: dict[str, float] | None = None,
    cancellation: CancellationToken | None = None,
) -> DispatcherResult:
    """Execute a ``WorkflowDecision`` — the Dispatcher's one entry point.

    Pure inputs, deterministic-shaped output; the only side effects are the
    target ``invoke`` calls themselves and one telemetry log line. Never
    raises (requirement 8). Timeouts are a Dispatcher-only concept — the
    Workflow Router (``work``/``decision``) carries no timeout field
    (requirement 9: "Workflow Router never knows timeouts").
    """
    start = time.monotonic()
    token = cancellation or CancellationToken()
    attempts: list[DispatchAttempt] = []
    transitions: list[Transition] = [
        Transition(DispatchState.PENDING, DispatchState.VALIDATED, "decision received")
    ]
    ctx = decision.routing_context

    # VALIDATED → BLOCKED: guardrail block / no target the router could select.
    # No fallback is attempted — decision.fallback_targets is already empty
    # here (the router's guardrail-filtered candidates were exhausted).
    if decision.selected_target is None:
        transitions.append(
            Transition(
                DispatchState.VALIDATED,
                DispatchState.BLOCKED,
                decision.guardrail_verdict,
            )
        )
        return _finish(
            decision,
            DispatchState.BLOCKED,
            None,
            None,
            attempts,
            transitions,
            0,
            decision.guardrail_verdict,
            False,
            start,
            ctx,
        )

    # VALIDATED → FAILED: dispatch-depth cap (requirement 5). The router
    # VALIDATES (exceeds_dispatch_cap is pure); the Dispatcher ENFORCES it here
    # — refused before any target is touched, never attempted, never recursed.
    new_ctx = replace(ctx, dispatch_depth=ctx.dispatch_depth + 1)
    if exceeds_dispatch_cap(new_ctx):
        reason = (
            f"dispatch depth {new_ctx.dispatch_depth} exceeds cap "
            f"{MAX_DISPATCH_DEPTH} — refusing to recurse"
        )
        transitions.append(
            Transition(DispatchState.VALIDATED, DispatchState.FAILED, reason)
        )
        return _finish(
            decision,
            DispatchState.FAILED,
            None,
            None,
            attempts,
            transitions,
            0,
            reason,
            False,
            start,
            new_ctx,
        )

    candidates = (decision.selected_target, *decision.fallback_targets)
    fallback_count = 0
    role = DispatchState.PRIMARY
    transitions.append(
        Transition(DispatchState.VALIDATED, DispatchState.PRIMARY, "attempting primary")
    )

    for i, name in enumerate(candidates):
        if i > 0:
            fallback_count += 1
            transitions.append(
                Transition(role, DispatchState.FALLBACK, f"trying fallback '{name}'")
            )
            role = DispatchState.FALLBACK

        if token.is_cancelled:
            transitions.append(
                Transition(role, DispatchState.FAILED, "cancelled before attempt")
            )
            return _finish(
                decision,
                DispatchState.FAILED,
                None,
                None,
                attempts,
                transitions,
                fallback_count,
                "cancelled",
                True,
                start,
                new_ctx,
            )

        target = registry.get(name)
        if target is None:
            attempts.append(DispatchAttempt(name, role, False, "target not registered"))
            continue

        available, avail_err = _safe_available(target)
        if not available:
            attempts.append(
                DispatchAttempt(name, role, False, avail_err or "unavailable")
            )
            continue

        per_timeout = (target_timeouts or {}).get(name, timeout_s)
        t0 = time.monotonic()
        result, error, cancelled = await _run_one(
            target, work, new_ctx, per_timeout, token
        )
        dur_ms = (time.monotonic() - t0) * 1000

        if cancelled:
            attempts.append(DispatchAttempt(name, role, False, "cancelled", dur_ms))
            transitions.append(
                Transition(role, DispatchState.FAILED, "cancelled mid-invoke")
            )
            return _finish(
                decision,
                DispatchState.FAILED,
                None,
                None,
                attempts,
                transitions,
                fallback_count,
                "cancelled",
                True,
                start,
                new_ctx,
            )

        if error is not None:
            attempts.append(DispatchAttempt(name, role, False, error, dur_ms))
            continue

        assert result is not None
        if result.success:
            attempts.append(DispatchAttempt(name, role, True, None, dur_ms))
            transitions.append(
                Transition(role, DispatchState.COMPLETED, f"'{name}' succeeded")
            )
            return _finish(
                decision,
                DispatchState.COMPLETED,
                name,
                result.output,
                attempts,
                transitions,
                fallback_count,
                None,
                False,
                start,
                new_ctx,
            )

        attempts.append(DispatchAttempt(name, role, False, result.error, dur_ms))

    if attempts:
        last = attempts[-1]
        reason = f"all candidates exhausted (last: {last.target} — {last.error})"
    else:
        reason = "no candidates to try"
    transitions.append(Transition(role, DispatchState.FAILED, reason))
    return _finish(
        decision,
        DispatchState.FAILED,
        None,
        None,
        attempts,
        transitions,
        fallback_count,
        reason,
        False,
        start,
        new_ctx,
    )


def _finish(
    decision: WorkflowDecision,
    state: DispatchState,
    target_used: str | None,
    output: str | None,
    attempts: list[DispatchAttempt],
    transitions: list[Transition],
    fallback_count: int,
    failure_reason: str | None,
    cancelled: bool,
    start: float,
    context: RoutingContext,
) -> DispatcherResult:
    result = DispatcherResult(
        trace_id=context.trace_id,
        category=decision.category.value,
        final_state=state,
        target_used=target_used,
        output=output,
        attempts=tuple(attempts),
        transitions=tuple(transitions),
        fallback_count=fallback_count,
        duration_ms=(time.monotonic() - start) * 1000,
        failure_reason=failure_reason,
        cancelled=cancelled,
        routing_context=context,
    )
    _log_dispatch(result)
    return result


def _log_dispatch(result: DispatcherResult) -> None:
    """One telemetry line per dispatch (requirement 7): trace_id, category,
    target, state, duration, fallback count, failure reason, completion status.
    ``trace_id`` is REUSED from the RoutingContext the Workflow Router already
    stamped — never a new id — so this line and the Provider Router's own
    ``route agent=workflow:<trace_id>:...`` debug line (ADR-012 §12) share the
    same correlator without either module importing the other's telemetry."""
    log.debug(
        "dispatch trace_id=%s category=%s target=%s state=%s duration_ms=%.1f "
        "fallback_count=%d failure_reason=%s",
        result.trace_id,
        result.category,
        result.target_used,
        result.final_state.value,
        result.duration_ms,
        result.fallback_count,
        result.failure_reason,
    )
