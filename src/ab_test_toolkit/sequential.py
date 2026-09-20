"""Sequential testing utilities — peeking-safe analysis for online experiments.

Provides an always-valid p-value via the mSPRT (mixture Sequential Probability
Ratio Test) construction with a Gaussian mixing distribution. This lets analysts
look at data continuously without inflating type-I error, which is the most common
mistake in CRO programs that stop tests early.

Reference: Johari, Pekelis, Walsh (2017), "Always Valid Inference: Bringing
Sequential Analysis to A/B Testing."
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp, log, sqrt


@dataclass
class SequentialSnapshot:
    """A single peek at the experiment."""

    visitors_control: int
    conversions_control: int
    visitors_treatment: int
    conversions_treatment: int


@dataclass
class SequentialResult:
    always_valid_p_value: float
    decision: str
    cumulative_visitors: int
    z_statistic: float
    tau_squared: float


DEFAULT_TAU = 0.01  # prior SD on the absolute lift: 1 percentage point


def always_valid_p_value(
    snapshot: SequentialSnapshot,
    tau_squared: float = DEFAULT_TAU**2,
) -> SequentialResult:
    """Compute an always-valid p-value using a Gaussian mSPRT.

    The mixture likelihood ratio for a two-sample difference in proportions
    ``theta_hat = p_t - p_c`` with a ``N(0, tau^2)`` prior on the true lift is

        Lambda_n = sqrt(sigma^2 / (sigma^2 + n*tau^2))
                   * exp( n^2 * tau^2 * theta_hat^2 / (2 * sigma^2 * (sigma^2 + n*tau^2)) )

    where ``sigma^2`` is the per-observation variance ``p(1-p)`` and ``n`` is the
    effective sample size ``1 / (1/n_c + 1/n_t)`` (so that ``sigma^2 / n`` equals
    the variance of ``theta_hat``). Substituting ``theta_hat^2 = z^2 * sigma^2 / n``
    gives the bounded, overflow-safe form used below:

        log Lambda_n = 0.5 * log(sigma^2 / (sigma^2 + n*tau^2))
                       + n * tau^2 * z^2 / (2 * (sigma^2 + n*tau^2))

    The always-valid p-value is ``min(1, 1 / Lambda_n)``.

    Args:
        snapshot: Cumulative counts at the moment of the peek.
        tau_squared: Prior variance of the absolute lift (conversion-rate units).
            The default corresponds to a prior SD of one percentage point, which is
            a sensible scale for most web conversion rates. Larger values give more
            power against big lifts and less against small ones.

    Returns:
        SequentialResult with the always-valid p-value and a decision string.
    """
    n_c = snapshot.visitors_control
    n_t = snapshot.visitors_treatment
    if n_c < 1 or n_t < 1:
        raise ValueError("Both arms must have at least 1 visitor.")
    if tau_squared <= 0:
        raise ValueError("tau_squared must be positive.")

    p_c = snapshot.conversions_control / n_c
    p_t = snapshot.conversions_treatment / n_t

    p_pool = (snapshot.conversions_control + snapshot.conversions_treatment) / (n_c + n_t)
    sigma_sq = p_pool * (1 - p_pool)  # per-observation variance under H0
    n_eff = 1.0 / (1.0 / n_c + 1.0 / n_t)
    se = sqrt(sigma_sq / n_eff) if sigma_sq > 0 else 0.0
    z = (p_t - p_c) / se if se > 0 else 0.0

    if sigma_sq == 0:
        # No variance at all (0% or 100% in both arms) -> nothing to learn yet.
        log_lambda = 0.0
    else:
        denom = sigma_sq + n_eff * tau_squared
        log_lambda = 0.5 * log(sigma_sq / denom) + (n_eff * tau_squared * z * z) / (2.0 * denom)

    # Always-valid p-value = min(1, 1/Lambda); computed in the log domain.
    av_p = 1.0 if log_lambda <= 0 else exp(-log_lambda)

    if av_p < 0.01:
        decision = "ship"
    elif av_p < 0.05:
        decision = "lean-ship"
    elif av_p > 0.5:
        decision = "no-effect-likely"
    else:
        decision = "keep-collecting"

    return SequentialResult(
        always_valid_p_value=av_p,
        decision=decision,
        cumulative_visitors=n_c + n_t,
        z_statistic=z,
        tau_squared=tau_squared,
    )


def peeking_correction_factor(num_peeks: int, alpha: float = 0.05) -> float:
    """Bonferroni-style correction factor for naively peeking.

    For comparison only — shows the inflated nominal alpha needed if a tester
    insists on running num_peeks fixed-horizon tests instead of using the always-valid
    construction above.

    Args:
        num_peeks: How many times the analyst checked significance.
        alpha: Desired family-wise alpha.

    Returns:
        Per-peek alpha required to keep family-wise alpha at the desired level.
    """
    if num_peeks < 1:
        raise ValueError("num_peeks must be >= 1.")
    return alpha / num_peeks


def run_sequence(snapshots: list[SequentialSnapshot], tau_squared: float = DEFAULT_TAU**2):
    """Replay a sequence of peeks. Useful for plotting decision trajectories."""
    out = []
    for snap in snapshots:
        out.append(always_valid_p_value(snap, tau_squared=tau_squared))
    return out
