"""Tests for the business impact model — confidence must accompany every
estimate."""

from __future__ import annotations

import pytest

from app.synthesis.business_impact import assess_business_impact, coverage
from app.synthesis.errors import SynthesisError
from app.synthesis.models import BusinessImpactDimension as D
from app.synthesis.models import BusinessImpactEstimate


def test_assess_business_impact_computes_overall_confidence():
    assessment = assess_business_impact(
        "rec-1",
        (
            BusinessImpactEstimate(
                dimension=D.REVENUE, estimate="+$2M", confidence=0.8
            ),
            BusinessImpactEstimate(dimension=D.COST, estimate="+$500K", confidence=0.6),
        ),
    )
    assert abs(assessment.overall_confidence - 0.7) < 1e-9


def test_requires_at_least_one_estimate():
    with pytest.raises(SynthesisError):
        assess_business_impact("rec-1", ())


def test_rejects_duplicate_dimension():
    with pytest.raises(SynthesisError):
        assess_business_impact(
            "rec-1",
            (
                BusinessImpactEstimate(
                    dimension=D.REVENUE, estimate="a", confidence=0.5
                ),
                BusinessImpactEstimate(
                    dimension=D.REVENUE, estimate="b", confidence=0.5
                ),
            ),
        )


def test_rejects_out_of_range_confidence():
    with pytest.raises(SynthesisError):
        assess_business_impact(
            "rec-1",
            (
                BusinessImpactEstimate(
                    dimension=D.REVENUE, estimate="a", confidence=1.5
                ),
            ),
        )


def test_coverage_reflects_fraction_of_8_dimensions():
    assessment = assess_business_impact(
        "rec-1",
        (BusinessImpactEstimate(dimension=D.REVENUE, estimate="a", confidence=0.5),),
    )
    assert coverage(assessment) == 1 / 8


def test_full_coverage_with_all_8_dimensions():
    estimates = tuple(
        BusinessImpactEstimate(dimension=d, estimate="x", confidence=0.5) for d in D
    )
    assessment = assess_business_impact("rec-1", estimates)
    assert coverage(assessment) == 1.0
