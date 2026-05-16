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
    assert res.decision in ("keep-collecting", "no-effect-likely")


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
