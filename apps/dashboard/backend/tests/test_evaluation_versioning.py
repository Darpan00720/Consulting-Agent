"""Tests for the Evaluation Platform versioning ledger."""

from __future__ import annotations

import pytest

from app.evaluation.case_library import all_benchmark_cases
from app.evaluation.errors import DuplicateCaseError, UnknownCaseError
from app.evaluation.evaluation import evaluate_replay
from app.evaluation.replay import replay_case
from app.evaluation.versioning import EvaluationVersioningLedger


def test_register_and_deprecate_case_version():
    case = all_benchmark_cases()[0]
    ledger = EvaluationVersioningLedger()
    info = ledger.register_case_version(case)
    assert info.deprecated is False

    updated = ledger.mark_case_deprecated(
        case.case_id, case.version, replaced_by="case-v2", reason="superseded"
    )
    assert updated.deprecated is True
    assert updated.replaced_by == "case-v2"
    # history is append-only: both entries survive
    history = ledger.case_version_history(case.case_id)
    assert len(history) == 1  # same version updated in place, never duplicated
    assert history[0].deprecated is True


def test_register_case_version_rejects_duplicate():
    case = all_benchmark_cases()[0]
    ledger = EvaluationVersioningLedger()
    ledger.register_case_version(case)
    with pytest.raises(DuplicateCaseError):
        ledger.register_case_version(case)


def test_mark_case_deprecated_rejects_unknown_case():
    ledger = EvaluationVersioningLedger()
    with pytest.raises(UnknownCaseError):
        ledger.mark_case_deprecated("ghost", "1.0.0")


def test_metric_version_registration_and_lookup():
    ledger = EvaluationVersioningLedger()
    info = ledger.register_metric_version("1.0.0", {"traceability": 0.1})
    assert ledger.metric_version("1.0.0") is info
    assert ledger.metric_version("no-such-version") is None
    with pytest.raises(DuplicateCaseError):
        ledger.register_metric_version("1.0.0", {"traceability": 0.2})


def test_evaluation_history_is_chronologically_ordered():
    case = all_benchmark_cases()[0]
    replay = replay_case(case)
    e1 = evaluate_replay(case, replay)
    ledger = EvaluationVersioningLedger()
    ledger.record_evaluation(e1)
    history = ledger.evaluation_history_for(case.case_id)
    assert history == (e1,)
    assert ledger.latest_evaluation_for(case.case_id) is e1
    assert ledger.latest_evaluation_for("no-such-case") is None
