"""Frequentist analysis for two-variant A/B tests.

Provides:
- two-proportion z-test (pooled and unpooled)
- sample-size calculator for proportions (one-sided and two-sided)
- two-sample Welch t-test for revenue / continuous metrics
- confidence intervals for proportion difference and relative lift
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from math import sqrt
from typing import Optional

import numpy as np
from scipy import stats


@dataclass
class VariantSummary:
    """Aggregate counts for one variant in a proportion experiment."""

    name: str
    visitors: int
    conversions: int

    @property
    def rate(self) -> float:
        if self.visitors == 0:
            return 0.0
        return self.conversions / self.visitors

    def validate(self) -> None:
        if self.visitors <= 0:
            raise ValueError(f"Variant '{self.name}' has non-positive visitors: {self.visitors}")
        if self.conversions < 0:
            raise ValueError(f"Variant '{self.name}' has negative conversions: {self.conversions}")
        if self.conversions > self.visitors:
            raise ValueError(
                f"Variant '{self.name}' has more conversions ({self.conversions}) "
                f"than visitors ({self.visitors})."
            )


@dataclass
class FrequentistResult:
    """Result of a frequentist two-proportion test."""

    control: VariantSummary
    treatment: VariantSummary
    absolute_diff: float
    relative_lift: float
    z_statistic: float
    p_value_two_sided: float
    p_value_one_sided: float
    ci95_absolute: tuple
    ci95_relative: tuple
    alpha: float
    significant_two_sided: bool
    significant_one_sided: bool
    method: str = "two-proportion-z-test"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["control"] = asdict(self.control)
        d["treatment"] = asdict(self.treatment)
        d["control"]["rate"] = self.control.rate
        d["treatment"]["rate"] = self.treatment.rate
        return d


def two_proportion_z_test(
    control: VariantSummary,
    treatment: VariantSummary,
    alpha: float = 0.05,
    pooled: bool = True,
) -> FrequentistResult:
    """Run a two-proportion z-test for a conversion-rate A/B test.

    Args:
        control: Control variant counts.
        treatment: Treatment variant counts.
        alpha: Significance threshold (two-sided unless specified).
        pooled: Use pooled variance (default, common in CRO calculators).

    Returns:
        FrequentistResult with z-statistic, p-values, CIs, and significance flags.
    """
    control.validate()
    treatment.validate()

    p_c = control.rate
    p_t = treatment.rate
    n_c = control.visitors
    n_t = treatment.visitors

    if pooled:
        p_pool = (control.conversions + treatment.conversions) / (n_c + n_t)
        se = sqrt(p_pool * (1 - p_pool) * (1 / n_c + 1 / n_t))
    else:
        se = sqrt(p_c * (1 - p_c) / n_c + p_t * (1 - p_t) / n_t)

    abs_diff = p_t - p_c
    rel_lift = abs_diff / p_c if p_c > 0 else float("inf")

    if se == 0:
        z = 0.0
    else:
        z = abs_diff / se

    p_two = 2.0 * (1.0 - stats.norm.cdf(abs(z)))
    p_one = 1.0 - stats.norm.cdf(z)

    # Confidence intervals use UNpooled SE for the difference
    se_unpooled = sqrt(p_c * (1 - p_c) / n_c + p_t * (1 - p_t) / n_t)
    margin = stats.norm.ppf(1 - alpha / 2) * se_unpooled
    ci_abs = (abs_diff - margin, abs_diff + margin)

    if p_c > 0:
        ci_rel = (ci_abs[0] / p_c, ci_abs[1] / p_c)
    else:
        ci_rel = (float("-inf"), float("inf"))

    return FrequentistResult(
        control=control,
        treatment=treatment,
        absolute_diff=abs_diff,
        relative_lift=rel_lift,
        z_statistic=z,
        p_value_two_sided=p_two,
        p_value_one_sided=p_one,
        ci95_absolute=ci_abs,
        ci95_relative=ci_rel,
        alpha=alpha,
        significant_two_sided=p_two < alpha,
        significant_one_sided=p_one < alpha,
    )


def required_sample_size_proportion(
    baseline_rate: float,
    minimum_detectable_effect: float,
    alpha: float = 0.05,
    power: float = 0.8,
    two_sided: bool = True,
    effect_is_relative: bool = True,
) -> int:
    """Compute the per-variant sample size required to detect a given effect.

    Args:
        baseline_rate: Control conversion rate (0..1).
        minimum_detectable_effect: MDE. Interpreted as a relative lift by default
            (e.g. 0.10 == +10% relative). Set effect_is_relative=False to treat
            as absolute percentage points.
        alpha: Significance threshold.
        power: Statistical power (1 - beta).
        two_sided: Use two-sided z-critical value.
        effect_is_relative: Whether MDE is relative or absolute.

    Returns:
        Sample size per variant (rounded up to int).
    """
    if not (0 < baseline_rate < 1):
        raise ValueError("baseline_rate must be between 0 and 1 exclusive.")
    if minimum_detectable_effect <= 0:
        raise ValueError("minimum_detectable_effect must be positive.")

    if effect_is_relative:
        treated_rate = baseline_rate * (1 + minimum_detectable_effect)
    else:
        treated_rate = baseline_rate + minimum_detectable_effect

    if not (0 < treated_rate < 1):
        raise ValueError(
            f"Resulting treated rate {treated_rate:.4f} must be in (0,1). "
            "Reduce MDE or baseline_rate."
        )

    z_alpha = stats.norm.ppf(1 - alpha / 2) if two_sided else stats.norm.ppf(1 - alpha)
    z_beta = stats.norm.ppf(power)

    p_bar = (baseline_rate + treated_rate) / 2.0
    numerator = (
        z_alpha * sqrt(2 * p_bar * (1 - p_bar))
        + z_beta * sqrt(baseline_rate * (1 - baseline_rate) + treated_rate * (1 - treated_rate))
    ) ** 2
    denominator = (treated_rate - baseline_rate) ** 2
    n_per_variant = numerator / denominator
    return int(np.ceil(n_per_variant))


@dataclass
class WelchResult:
    """Result of a Welch t-test for two independent samples."""

    mean_control: float
    mean_treatment: float
    diff: float
    relative_lift: float
    t_statistic: float
    df: float
    p_value_two_sided: float
    p_value_one_sided: float
    ci95: tuple
    alpha: float
    significant_two_sided: bool


def welch_t_test(
    control_values: np.ndarray,
    treatment_values: np.ndarray,
    alpha: float = 0.05,
) -> WelchResult:
    """Welch's two-sample t-test for unequal variance.

    Use for revenue-per-visitor, AOV, time-on-page, and similar continuous metrics.

    Args:
        control_values: 1-D array of per-unit observations from control.
        treatment_values: 1-D array of per-unit observations from treatment.
        alpha: Significance threshold (two-sided).

    Returns:
        WelchResult.
    """
    c = np.asarray(control_values, dtype=float)
    t = np.asarray(treatment_values, dtype=float)
    if c.size < 2 or t.size < 2:
        raise ValueError("Both samples must have at least 2 observations.")

    mean_c = float(np.mean(c))
    mean_t = float(np.mean(t))
    var_c = float(np.var(c, ddof=1))
    var_t = float(np.var(t, ddof=1))
    n_c = c.size
    n_t = t.size

    se = sqrt(var_c / n_c + var_t / n_t)
    if se == 0:
        t_stat = 0.0
    else:
        t_stat = (mean_t - mean_c) / se

    # Welch-Satterthwaite df
    df_num = (var_c / n_c + var_t / n_t) ** 2
    df_den = (var_c / n_c) ** 2 / (n_c - 1) + (var_t / n_t) ** 2 / (n_t - 1)
    df = df_num / df_den if df_den > 0 else 1

    p_two = 2.0 * (1.0 - stats.t.cdf(abs(t_stat), df))
    p_one = 1.0 - stats.t.cdf(t_stat, df)

    margin = stats.t.ppf(1 - alpha / 2, df) * se
    diff = mean_t - mean_c
    ci = (diff - margin, diff + margin)
    rel = diff / mean_c if mean_c != 0 else float("inf")

    return WelchResult(
        mean_control=mean_c,
        mean_treatment=mean_t,
        diff=diff,
        relative_lift=rel,
        t_statistic=t_stat,
        df=float(df),
        p_value_two_sided=float(p_two),
        p_value_one_sided=float(p_one),
        ci95=ci,
        alpha=alpha,
        significant_two_sided=p_two < alpha,
    )
