"""Revenue impact analysis on top of conversion-rate experiments.

Most online A/B calculators stop at "did conversion rate move?". This module
adds:
- revenue per visitor (RPV) projections and CIs via the delta method
- annualized revenue impact at a forecast traffic level
- per-variant AOV (Average Order Value) bootstrap for confidence

Inputs accept GA4-style per-session revenue arrays.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from math import sqrt
from typing import Optional

import numpy as np


@dataclass
class RevenueResult:
    rpv_control: float
    rpv_treatment: float
    rpv_diff: float
    rpv_diff_se: float
    rpv_diff_ci95: tuple
    annualized_impact: float
    annualized_impact_low: float
    annualized_impact_high: float
    aov_control: float
    aov_treatment: float
    converters_control: int
    converters_treatment: int

    def to_dict(self) -> dict:
        return asdict(self)


def revenue_per_visitor_delta(
    control_revenue: np.ndarray,
    treatment_revenue: np.ndarray,
    annual_traffic_forecast: int,
    confidence: float = 0.95,
) -> RevenueResult:
    """Estimate revenue-per-visitor differences and annualize them.

    Args:
        control_revenue: Array of per-visitor revenue (0 for non-converters).
        treatment_revenue: Array of per-visitor revenue (0 for non-converters).
        annual_traffic_forecast: Visitors expected over a full year to extrapolate.
        confidence: CI level (default 95%).

    Returns:
        RevenueResult.
    """
    c = np.asarray(control_revenue, dtype=float)
    t = np.asarray(treatment_revenue, dtype=float)
    if c.size < 2 or t.size < 2:
        raise ValueError("Both samples must have at least 2 observations.")

    mean_c = float(np.mean(c))
    mean_t = float(np.mean(t))
    var_c = float(np.var(c, ddof=1))
    var_t = float(np.var(t, ddof=1))

    diff = mean_t - mean_c
    se_diff = sqrt(var_c / c.size + var_t / t.size)

    from scipy import stats as _stats

    z = _stats.norm.ppf(1.0 - (1.0 - confidence) / 2.0)
    ci = (diff - z * se_diff, diff + z * se_diff)

    annual = diff * annual_traffic_forecast
    annual_lo = ci[0] * annual_traffic_forecast
    annual_hi = ci[1] * annual_traffic_forecast

    converters_c = int(np.sum(c > 0))
    converters_t = int(np.sum(t > 0))
    aov_c = float(np.sum(c) / converters_c) if converters_c else 0.0
    aov_t = float(np.sum(t) / converters_t) if converters_t else 0.0

    return RevenueResult(
        rpv_control=mean_c,
        rpv_treatment=mean_t,
        rpv_diff=diff,
        rpv_diff_se=se_diff,
        rpv_diff_ci95=ci,
        annualized_impact=annual,
        annualized_impact_low=annual_lo,
        annualized_impact_high=annual_hi,
        aov_control=aov_c,
        aov_treatment=aov_t,
        converters_control=converters_c,
        converters_treatment=converters_t,
    )


def bootstrap_rpv_diff(
    control_revenue: np.ndarray,
    treatment_revenue: np.ndarray,
    iterations: int = 5000,
    seed: int = 7,
    confidence: float = 0.95,
) -> tuple:
    """Bootstrap a confidence interval for RPV difference (robust to skewed revenue).

    Args:
        control_revenue: Per-visitor revenue for control.
        treatment_revenue: Per-visitor revenue for treatment.
        iterations: Bootstrap iterations.
        seed: RNG seed.
        confidence: CI level.

    Returns:
        (low, high) tuple at the requested confidence level.
    """
    rng = np.random.default_rng(seed)
    c = np.asarray(control_revenue, dtype=float)
    t = np.asarray(treatment_revenue, dtype=float)

    diffs = np.empty(iterations, dtype=float)
    n_c = c.size
    n_t = t.size
    for i in range(iterations):
        idx_c = rng.integers(0, n_c, n_c)
        idx_t = rng.integers(0, n_t, n_t)
        diffs[i] = float(np.mean(t[idx_t]) - np.mean(c[idx_c]))

    lo = float(np.percentile(diffs, (1.0 - confidence) / 2.0 * 100.0))
    hi = float(np.percentile(diffs, (1.0 - (1.0 - confidence) / 2.0) * 100.0))
    return (lo, hi)
