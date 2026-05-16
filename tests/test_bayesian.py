"""Tests for bayesian module."""

import pytest

from ab_test_toolkit.bayesian import (
    BayesianPrior,
    analyze,
    update_posterior,
    credible_interval,
    decision_threshold_loss,
)


def test_update_posterior_conjugacy():
    prior = BayesianPrior(1.0, 1.0)
    post = update_posterior(prior, conversions=10, visitors=100)
    assert post.alpha == 11.0
    assert post.beta == 91.0


def test_update_posterior_invalid():
    prior = BayesianPrior()
    with pytest.raises(ValueError):
        update_posterior(prior, conversions=11, visitors=10)
    with pytest.raises(ValueError):
        update_posterior(prior, conversions=-1, visitors=10)


def test_credible_interval_uniform_prior():
    prior = BayesianPrior(1.0, 1.0)
    lo, hi = credible_interval(prior, level=0.95)
    # Uniform Beta(1,1) on [0,1], 95% credible should be ~ [0.025, 0.975]
    assert lo == pytest.approx(0.025, abs=1e-3)
    assert hi == pytest.approx(0.975, abs=1e-3)


def test_analyze_clear_winner():
    res = analyze(
        control_conversions=200,
        control_visitors=5000,
        treatment_conversions=400,
        treatment_visitors=5000,
        samples=20000,
    )
    assert res.prob_treatment_beats_control > 0.99
    assert res.expected_uplift_absolute > 0
    assert res.expected_loss_choosing_treatment < res.expected_loss_choosing_control


def test_analyze_tie():
    res = analyze(
        control_conversions=200,
        control_visitors=5000,
        treatment_conversions=200,
        treatment_visitors=5000,
        samples=20000,
    )
    # Should be roughly 50/50
    assert 0.4 < res.prob_treatment_beats_control < 0.6


def test_decision_threshold_loss():
    # Loss much smaller than tolerable -> ship
    assert decision_threshold_loss(0.0001, 0.01) == "ship"
    # Loss close to tolerable -> keep-testing
    assert decision_threshold_loss(0.005, 0.01) == "keep-testing"
    # Loss above tolerable -> kill
    assert decision_threshold_loss(0.02, 0.01) == "kill"
