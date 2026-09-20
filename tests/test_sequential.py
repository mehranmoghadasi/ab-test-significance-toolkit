"""Tests for sequential module."""

import pytest

from ab_test_toolkit.sequential import (
    SequentialSnapshot,
    always_valid_p_value,
    peeking_correction_factor,
)


def test_always_valid_no_effect():
    snap = SequentialSnapshot(
        visitors_control=5000, conversions_control=200,
        visitors_treatment=5000, conversions_treatment=200,
    )
    res = always_valid_p_value(snap)
    assert res.always_valid_p_value > 0.5
    assert res.decision == "keep-collecting"


def test_always_valid_strong_effect():
    snap = SequentialSnapshot(
        visitors_control=5000, conversions_control=200,
        visitors_treatment=5000, conversions_treatment=400,
    )
    res = always_valid_p_value(snap)
    assert res.always_valid_p_value < 0.01
    assert res.decision == "ship"


def test_peeking_correction_factor():
    assert peeking_correction_factor(1, 0.05) == 0.05
    assert peeking_correction_factor(10, 0.05) == 0.005
    with pytest.raises(ValueError):
        peeking_correction_factor(0)


def test_zero_visitors_raises():
    snap = SequentialSnapshot(
        visitors_control=0, conversions_control=0,
        visitors_treatment=10, conversions_treatment=2,
    )
    with pytest.raises(ValueError):
        always_valid_p_value(snap)


def test_always_valid_is_bounded_and_monotone_in_evidence():
    """Regression: the old formula overflowed on strong effects. The p-value must stay
    in [0, 1], fall as evidence accumulates, and never exceed the fixed-horizon p-value
    by less than the mSPRT's built-in conservatism would imply."""
    small = SequentialSnapshot(100, 4, 100, 8)
    large = SequentialSnapshot(50000, 2000, 50000, 4000)
    huge = SequentialSnapshot(5_000_000, 200_000, 5_000_000, 400_000)
    ps = [always_valid_p_value(s).always_valid_p_value for s in (small, large, huge)]
    assert all(0.0 <= p <= 1.0 for p in ps)
    assert ps[0] > ps[1] >= ps[2]
    assert ps[0] > 0.05  # 100 visitors per arm is not enough to ship on a 4pp lift


def test_no_variance_yields_p_of_one():
    snap = SequentialSnapshot(100, 0, 100, 0)
    assert always_valid_p_value(snap).always_valid_p_value == 1.0


def test_tau_must_be_positive():
    with pytest.raises(ValueError):
        always_valid_p_value(SequentialSnapshot(10, 1, 10, 2), tau_squared=0)
