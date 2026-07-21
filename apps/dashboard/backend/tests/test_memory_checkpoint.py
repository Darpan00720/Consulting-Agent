"""Tests for the shared ``app.memory.checkpoint`` helper — extracted by the
2026-07-19 architecture review from 4 independently-duplicated
checkpoint_X/resume_X implementations (consulting, synthesis, deliverables,
evaluation)."""

from __future__ import annotations

import asyncio

import pytest

from app import config, db
from app.memory.checkpoint import load_checkpoint, store_checkpoint


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "checkpoint-test.db")
    db.reset_for_tests()


def _run(coro):
    return asyncio.run(coro)


def test_store_and_load_round_trips_a_payload():
    result = _run(store_checkpoint("k1", {"a": 1}, trace_id="t1", metadata={"x": "y"}))
    assert result.success

    value = _run(load_checkpoint("k1"))
    assert value == {"a": 1}


def test_load_missing_key_returns_none_not_an_exception():
    value = _run(load_checkpoint("never-stored"))
    assert value is None


def test_store_without_metadata_or_trace_id_still_succeeds():
    result = _run(store_checkpoint("k2", "plain-string-payload"))
    assert result.success
    assert _run(load_checkpoint("k2")) == "plain-string-payload"


def test_two_keys_do_not_collide():
    _run(store_checkpoint("a", "first"))
    _run(store_checkpoint("b", "second"))
    assert _run(load_checkpoint("a")) == "first"
    assert _run(load_checkpoint("b")) == "second"


def test_checkpoint_writes_land_under_reserved_namespace_not_callers_engagement_id():
    """ADR-014 Phase 0 database-safety requirement: a W7-W12 checkpoint must
    never appear, in the shared app.db event log, as if it belonged to the
    caller's own engagement_id — it must be physically isolated under a
    reserved namespace so it can never be mistaken for a real app.pipeline
    phase-completion event, even under an identical engagement_id."""
    from app import db

    engagement_id = "e1"
    key = f"{engagement_id}::checkpoint::latest"
    _run(store_checkpoint(key, {"stage": "problem_definition"}))

    # nothing lands under the caller's own naive engagement_id
    assert db.list_events(engagement_id) == []

    # it lands, instead, under the reserved namespace
    reserved_events = db.list_events("__w7w12_reserved__")
    assert len(reserved_events) == 1
    assert reserved_events[0]["type"] == "phase_completed"
    assert reserved_events[0]["payload"]["phase"] == key
    assert reserved_events[0]["payload"]["output"] == {"stage": "problem_definition"}
