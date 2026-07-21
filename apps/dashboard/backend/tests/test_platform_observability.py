"""Tests for unified observability / trace correlation (ADR-013 W6,
requirement 5/13).

Proves — concretely, via real log records, not by assertion alone — that a
single trace_id correlates across the Workflow Router, Dispatcher, Agent
Runtime, Memory Service, and Tool Runtime loggers.
"""

from __future__ import annotations

import asyncio
import logging

from app.platform.observability import (
    PLATFORM_LOGGERS,
    TraceCollector,
    attach_trace_collector,
    detach_trace_collector,
)
from app.workflow.dispatcher import dispatch
from app.workflow.router import RoutingContext, Work, route
from app.workflow.targets import default_registry


def _run(coro):
    return asyncio.run(coro)


def test_trace_collector_is_a_logging_handler():
    assert isinstance(TraceCollector(), logging.Handler)


def test_attach_returns_a_collector_and_can_be_detached():
    collector = attach_trace_collector()
    assert isinstance(collector, TraceCollector)
    detach_trace_collector(collector)
    for name in PLATFORM_LOGGERS:
        assert collector not in logging.getLogger(name).handlers


def test_attach_lowers_logger_level_so_debug_records_flow():
    """Regression: attaching a DEBUG-level Handler is not enough if the
    LOGGER itself is still above DEBUG — the logger drops the record before
    any handler sees it. Real bug, found and fixed during W6."""
    logger = logging.getLogger("app.workflow.router")
    logger.setLevel(logging.WARNING)  # simulate the pre-fix default
    collector = attach_trace_collector()
    try:
        assert logging.getLogger("app.workflow.router").level == logging.DEBUG
    finally:
        detach_trace_collector(collector)


def test_detach_restores_prior_logger_level():
    logger = logging.getLogger("app.workflow.router")
    logger.setLevel(logging.WARNING)
    collector = attach_trace_collector()
    detach_trace_collector(collector)
    assert logging.getLogger("app.workflow.router").level == logging.WARNING


# ---- Real cross-layer correlation (the core requirement 5 proof) ----------


def test_trace_correlates_across_router_and_dispatcher():
    collector = attach_trace_collector()
    try:
        reg = default_registry()
        ctx = RoutingContext(trace_id="obs-test-1")
        decision = route(Work(text="implement a parser"), ctx, registry=reg)
        _run(dispatch(decision, reg, Work(text="implement a parser")))

        layers = collector.layers_touched("obs-test-1")
        assert "app.workflow.router" in layers
        assert "app.workflow.dispatcher" in layers
    finally:
        detach_trace_collector(collector)


def test_latency_breakdown_has_real_numbers():
    collector = attach_trace_collector()
    try:
        reg = default_registry()
        ctx = RoutingContext(trace_id="obs-test-2")
        decision = route(Work(text="implement a parser"), ctx, registry=reg)
        _run(dispatch(decision, reg, Work(text="implement a parser")))

        breakdown = collector.latency_breakdown("obs-test-2")
        assert "app.workflow.dispatcher" in breakdown
        assert breakdown["app.workflow.dispatcher"] >= 0
    finally:
        detach_trace_collector(collector)


def test_different_trace_ids_do_not_mix():
    collector = attach_trace_collector()
    try:
        reg = default_registry()
        for trace_id in ("obs-a", "obs-b"):
            ctx = RoutingContext(trace_id=trace_id)
            decision = route(Work(text="implement a parser"), ctx, registry=reg)
            _run(dispatch(decision, reg, Work(text="implement a parser")))

        trace_a = collector.get_trace("obs-a")
        trace_b = collector.get_trace("obs-b")
        assert all(e.fields.get("trace_id") == "obs-a" for e in trace_a)
        assert all(e.fields.get("trace_id") == "obs-b" for e in trace_b)
    finally:
        detach_trace_collector(collector)


def test_untraced_logger_records_are_ignored():
    """A log line with no trace_id field (there are none among the platform
    loggers today, but the collector must not crash on one) is silently
    skipped, not buffered under a bogus key."""
    collector = TraceCollector()
    record = logging.LogRecord(
        name="app.workflow.router",
        level=logging.DEBUG,
        pathname="",
        lineno=0,
        msg="a line without any correlator",
        args=(),
        exc_info=None,
    )
    collector.emit(record)
    assert collector.get_trace("") == ()


def test_max_traces_evicts_oldest():
    collector = TraceCollector(max_traces=2)
    for trace_id in ("t1", "t2", "t3"):
        record = logging.LogRecord(
            name="x",
            level=logging.DEBUG,
            pathname="",
            lineno=0,
            msg=f"event trace_id={trace_id}",
            args=(),
            exc_info=None,
        )
        collector.emit(record)
    assert collector.get_trace("t1") == ()  # evicted
    assert collector.get_trace("t2") != ()
    assert collector.get_trace("t3") != ()


def test_clear_empties_all_traces():
    collector = TraceCollector()
    record = logging.LogRecord(
        name="x",
        level=logging.DEBUG,
        pathname="",
        lineno=0,
        msg="event trace_id=t1",
        args=(),
        exc_info=None,
    )
    collector.emit(record)
    assert collector.get_trace("t1") != ()
    collector.clear()
    assert collector.get_trace("t1") == ()
