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
from math import sqrt, log, pi, exp
from typing import List

from scipy import stats


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


def always_valid_p_value(
    snapshot: SequentialSnapshot,
    tau_squared: float = 1.0,
) -> SequentialResult:
    """Compute an always-valid p-value using a Gaussian mSPRT.

    Args:
        snapshot: Cumulative counts at the moment of the peek.
        tau_squared: Variance of the Gaussian mixing distribution over the alternative
            effect. Larger tau_squared = better power against larger effects, weaker
            against small effects. 1.0 is a reasonable default for proportion tests
            with the lift measured in standard-deviation units.

    Returns:
        SequentialResult with the always-valid p-value and a decision string.
    """
    n_c = snapshot.visitors_control
    n_t = snapshot.visitors_treatment
    if n_c < 1 or n_t < 1:
        raise ValueError("Both arms must have at least 1 visitor.")

    p_c = snapshot.conversions_control / n_c
    p_t = snapshot.conversions_treatment / n_t

    p_pool = (snapshot.conversions_control + snapshot.conversions_treatment) / (n_c + n_t)
    se = sqrt(p_pool * (1 - p_pool) * (1 / n_c + 1 / n_t))
    if se == 0:
        z = 0.0
    else:
        z = (p_t - p_c) / se

    n = n_c + n_t  # effective sample
    # mSPRT statistic with N(0, tau^2) mixing prior on the effect:
    # m_n = sqrt(V / (V + n*tau^2)) * exp( n^2 * tau^2 * z^2 / (2 * V * (V + n*tau^2)) )
    # with V = 1 under standardized z. We work in the log domain for stability.
    V = 1.0
    log_msprt = 0.5 * (log(V) - log(V + n * tau_squared)) + (
        (n * n * tau_squared * z * z) / (2.0 * V * (V + n * tau_squared))
    )
    msprt = exp(log_msprt)

    # Always-valid p-value: min(1, 1/msprt), clipped to [0,1].
    av_p = min(1.0, 1.0 / msprt) if msprt > 0 else 1.0

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
        cumulative_visitors=n,
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


def run_sequence(snapshots: List[SequentialSnapshot], tau_squared: float = 1.0):
    """Replay a sequence of peeks. Useful for plotting decision trajectories."""
    out = []
    for snap in snapshots:
        out.append(always_valid_p_value(snap, tau_squared=tau_squared))
    return out
