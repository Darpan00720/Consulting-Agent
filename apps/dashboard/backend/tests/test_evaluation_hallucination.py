"""Tests for the 8-type Hallucination Detection engine."""

from __future__ import annotations

import dataclasses

from app.evaluation.case_library import all_benchmark_cases
from app.evaluation.hallucination import detect_hallucinations
from app.evaluation.models import HallucinationType
from app.evaluation.replay import replay_case, replay_case_with_state


def test_clean_replay_reports_no_invented_evidence_or_metrics():
    case = all_benchmark_cases()[0]
    replay = replay_case(case)
    findings = detect_hallucinations(case, replay)
    assert findings == ()


def test_invented_evidence_detected_when_finding_is_not_grounded():
    case = all_benchmark_cases()[0]
    replay = replay_case(case)
    bad = dataclasses.replace(
        replay, findings=(*replay.findings, "a fabricated finding never in the case")
    )
    findings = detect_hallucinations(case, bad)
    assert any(
        f.hallucination_type == HallucinationType.INVENTED_EVIDENCE for f in findings
    )
    invented = next(
        f
        for f in findings
        if f.hallucination_type == HallucinationType.INVENTED_EVIDENCE
    )
    assert "a fabricated finding never in the case" in invented.ref_ids


def test_invented_metric_detected_when_quality_metrics_has_unknown_key():
    case = all_benchmark_cases()[0]
    replay = replay_case(case)
    bad = dataclasses.replace(
        replay, quality_metrics={**replay.quality_metrics, "made_up_score": 0.99}
    )
    findings = detect_hallucinations(case, bad)
    assert any(
        f.hallucination_type == HallucinationType.INVENTED_METRIC for f in findings
    )


def test_state_dependent_checks_skipped_without_live_state():
    case = all_benchmark_cases()[0]
    replay = replay_case(case)
    findings = detect_hallucinations(case, replay, state=None)
    types_found = {f.hallucination_type for f in findings}
    assert HallucinationType.MISSING_ASSUMPTIONS not in types_found


def test_missing_assumptions_surfaces_with_live_state():
    case = all_benchmark_cases()[0]
    replay, state = replay_case_with_state(case)
    findings = detect_hallucinations(case, replay, state=state)
    assert any(
        f.hallucination_type == HallucinationType.MISSING_ASSUMPTIONS for f in findings
    )


def test_unsupported_recommendation_reused_from_consistency():
    case = all_benchmark_cases()[0]
    replay, state = replay_case_with_state(case)
    import dataclasses as dc

    rec_id = next(iter(state.recommendations))
    state.recommendations[rec_id] = dc.replace(
        state.recommendations[rec_id],
        supporting_finding_ids=(),
        supporting_evidence_ids=(),
    )
    findings = detect_hallucinations(case, replay, state=state)
    assert any(
        f.hallucination_type == HallucinationType.UNSUPPORTED_RECOMMENDATION
        for f in findings
    )
