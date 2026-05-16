"""Bayesian Beta-Binomial analysis for conversion-rate A/B tests.

Provides:
- posterior Beta updates from observed counts
- P(treatment > control) and expected loss via Monte Carlo
- credible intervals for variant rates and uplift
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Tuple

import numpy as np
from scipy import stats


@dataclass
class BayesianPrior:
    """Beta(alpha, beta) prior. Defaults to a weakly-informative Jeffreys-style prior."""

    alpha: float = 1.0
    beta: float = 1.0


@dataclass
class BayesianResult:
    prob_treatment_beats_control: float
    expected_uplift_absolute: float
    expected_uplift_relative: float
    credible_interval_control: Tuple[float, float]
    credible_interval_treatment: Tuple[float, float]
    credible_interval_uplift_abs: Tuple[float, float]
    expected_loss_choosing_treatment: float
    expected_loss_choosing_control: float
    samples_drawn: int
    method: str = "beta-binomial-monte-carlo"

    def to_dict(self) -> dict:
        return asdict(self)


def update_posterior(prior: BayesianPrior, conversions: int, visitors: int) -> BayesianPrior:
    """Conjugate update for Beta(alpha, beta) given observed Bernoulli data.

    Args:
        prior: Beta prior.
        conversions: Number of successes.
        visitors: Number of trials.

    Returns:
        Posterior BayesianPrior.
    """
    if conversions < 0 or visitors < 0:
        raise ValueError("conversions and visitors must be non-negative.")
    if conversions > visitors:
        raise ValueError("conversions cannot exceed visitors.")
    return BayesianPrior(
        alpha=prior.alpha + conversions,
        beta=prior.beta + (visitors - conversions),
    )


def credible_interval(prior: BayesianPrior, level: float = 0.95) -> Tuple[float, float]:
    """Equal-tailed credible interval for a Beta distribution."""
    lower = (1.0 - level) / 2.0
    upper = 1.0 - lower
    lo = float(stats.beta.ppf(lower, prior.alpha, prior.beta))
    hi = float(stats.beta.ppf(upper, prior.alpha, prior.beta))
    return (lo, hi)


def analyze(
    control_conversions: int,
    control_visitors: int,
    treatment_conversions: int,
    treatment_visitors: int,
    prior: BayesianPrior = BayesianPrior(),
    samples: int = 100_000,
    seed: int = 42,
) -> BayesianResult:
    """Run a Bayesian Beta-Binomial A/B analysis.

    Args:
        control_conversions: Successes in control.
        control_visitors: Trials in control.
        treatment_conversions: Successes in treatment.
        treatment_visitors: Trials in treatment.
        prior: Beta prior (shared across variants).
        samples: Monte Carlo sample size.
        seed: RNG seed for reproducibility.

    Returns:
        BayesianResult with probabilities, credible intervals, and expected losses.
    """
    if samples < 1000:
        raise ValueError("samples must be >= 1000 for stable estimates.")

    rng = np.random.default_rng(seed)

    post_c = update_posterior(prior, control_conversions, control_visitors)
    post_t = update_posterior(prior, treatment_conversions, treatment_visitors)

    draws_c = rng.beta(post_c.alpha, post_c.beta, size=samples)
    draws_t = rng.beta(post_t.alpha, post_t.beta, size=samples)

    diff = draws_t - draws_c
    prob_better = float(np.mean(draws_t > draws_c))

    # Expected loss: if we pick treatment but control is actually better, by how much?
    loss_pick_t = float(np.mean(np.maximum(draws_c - draws_t, 0.0)))
    loss_pick_c = float(np.mean(np.maximum(draws_t - draws_c, 0.0)))

    rel = diff / draws_c
    # Drop infinities from rel uplift before percentiles
    rel = rel[np.isfinite(rel)]

    return BayesianResult(
        prob_treatment_beats_control=prob_better,
        expected_uplift_absolute=float(np.mean(diff)),
        expected_uplift_relative=float(np.mean(rel)) if rel.size else float("nan"),
        credible_interval_control=credible_interval(post_c),
        credible_interval_treatment=credible_interval(post_t),
        credible_interval_uplift_abs=(
            float(np.percentile(diff, 2.5)),
            float(np.percentile(diff, 97.5)),
        ),
        expected_loss_choosing_treatment=loss_pick_t,
        expected_loss_choosing_control=loss_pick_c,
        samples_drawn=samples,
    )


def decision_threshold_loss(expected_loss: float, tolerable_loss: float) -> str:
    """Translate an expected-loss number into a CRO recommendation.

    Args:
        expected_loss: From BayesianResult (e.g. expected_loss_choosing_treatment).
        tolerable_loss: Maximum acceptable expected loss (in same units as the metric).

    Returns:
        "ship", "keep-testing", or "kill".
    """
    if expected_loss <= tolerable_loss / 10.0:
        return "ship"
    if expected_loss <= tolerable_loss:
        return "keep-testing"
    return "kill"
