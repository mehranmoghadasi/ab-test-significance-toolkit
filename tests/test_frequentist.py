"""Tests for frequentist module."""

import numpy as np
import pytest

from ab_test_toolkit.frequentist import (
    VariantSummary,
    two_proportion_z_test,
    required_sample_size_proportion,
    welch_t_test,
)


def test_variant_summary_validation():
    v = VariantSummary(name="t", visitors=10, conversions=2)
    v.validate()
    assert v.rate == 0.2

    with pytest.raises(ValueError):
        VariantSummary(name="t", visitors=0, conversions=0).validate()
    with pytest.raises(ValueError):
        VariantSummary(name="t", visitors=10, conversions=11).validate()
    with pytest.raises(ValueError):
        VariantSummary(name="t", visitors=10, conversions=-1).validate()


def test_z_test_no_effect():
    c = VariantSummary("c", 5000, 200)
    t = VariantSummary("t", 5000, 200)
    res = two_proportion_z_test(c, t)
    assert abs(res.z_statistic) < 1e-9
    assert res.p_value_two_sided == pytest.approx(1.0, abs=1e-9)
    assert not res.significant_two_sided


def test_z_test_strong_effect():
    c = VariantSummary("c", 5000, 200)   # 4%
    t = VariantSummary("t", 5000, 400)   # 8%
    res = two_proportion_z_test(c, t)
    assert res.z_statistic > 5
    assert res.p_value_two_sided < 1e-6
    assert res.significant_two_sided
    assert res.relative_lift == pytest.approx(1.0, rel=1e-9)


def test_sample_size_proportion_basic():
    n = required_sample_size_proportion(0.04, 0.1, power=0.8, alpha=0.05)
    # 10% relative lift on a 4% baseline — known to require tens of thousands of visitors
    assert 25_000 < n < 80_000


def test_sample_size_proportion_absolute_effect():
    n_rel = required_sample_size_proportion(0.04, 0.1, effect_is_relative=True)
    n_abs = required_sample_size_proportion(0.04, 0.004, effect_is_relative=False)
    # 10% relative on a 4% baseline == +0.4 absolute pp, so they should be in the same ballpark
    assert 0.7 * n_rel < n_abs < 1.3 * n_rel


def test_sample_size_invalid_inputs():
    with pytest.raises(ValueError):
        required_sample_size_proportion(0.0, 0.1)
    with pytest.raises(ValueError):
        required_sample_size_proportion(0.04, 0.0)
    with pytest.raises(ValueError):
        # baseline + absolute effect must stay <1
        required_sample_size_proportion(0.95, 0.1, effect_is_relative=False)


def test_welch_t_test_basic():
    rng = np.random.default_rng(123)
    a = rng.normal(loc=10.0, scale=2.0, size=500)
    b = rng.normal(loc=10.5, scale=2.0, size=500)
    res = welch_t_test(a, b, alpha=0.05)
    assert res.diff > 0
    assert res.p_value_two_sided < 0.05
    assert res.significant_two_sided
