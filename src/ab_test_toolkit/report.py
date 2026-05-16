"""Render an exec-ready HTML report from a frequentist + Bayesian + revenue analysis.

Uses Jinja2 with an embedded template so the package has no external file deps.
The output is a single self-contained HTML file (no JS, no external CSS) so it
can be emailed or printed to PDF without further work.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from jinja2 import Environment, DictLoader, select_autoescape


REPORT_TEMPLATE = """\
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>A/B Test Report: {{ experiment_name }}</title>
<style>
  body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
       max-width:900px;margin:40px auto;color:#1d1d1d;padding:0 20px}
  h1{border-bottom:3px solid #0b6fbf;padding-bottom:8px}
  h2{margin-top:32px;color:#0b6fbf}
  .pill{display:inline-block;padding:4px 10px;border-radius:12px;font-size:13px;
        font-weight:600;color:#fff;background:#666}
  .pill.green{background:#1f9c5b}
  .pill.amber{background:#d68a00}
  .pill.red{background:#b53d3d}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:20px 0}
  .card{border:1px solid #e3e3e3;padding:16px;border-radius:8px}
  .card h3{margin:0 0 8px 0;font-size:14px;color:#555}
  .card .num{font-size:24px;font-weight:600}
  table{width:100%;border-collapse:collapse;margin-top:12px}
  th,td{padding:8px;border-bottom:1px solid #eee;text-align:left}
  th{background:#f6f8fa}
  .footnote{color:#888;font-size:12px;margin-top:40px;border-top:1px solid #eee;padding-top:12px}
  .recommend{padding:16px;border-left:4px solid #0b6fbf;background:#f3f8fc;border-radius:4px}
</style>
</head>
<body>
<h1>A/B Test Report: {{ experiment_name }}</h1>
<p><strong>Generated:</strong> {{ generated_at }} &nbsp; | &nbsp;
   <strong>Client:</strong> {{ client_name }}</p>

<h2>Headline</h2>
<div class="recommend">
  <strong>Recommendation:</strong>
  <span class="pill {{ recommendation_pill }}">{{ recommendation }}</span>
  &nbsp; — {{ recommendation_summary }}
</div>

<div class="grid">
  <div class="card">
    <h3>Control conversion rate</h3>
    <div class="num">{{ "%.2f%%"|format(freq.control.rate * 100) }}</div>
    <div>{{ freq.control.conversions }}/{{ freq.control.visitors }}</div>
  </div>
  <div class="card">
    <h3>Treatment conversion rate</h3>
    <div class="num">{{ "%.2f%%"|format(freq.treatment.rate * 100) }}</div>
    <div>{{ freq.treatment.conversions }}/{{ freq.treatment.visitors }}</div>
  </div>
  <div class="card">
    <h3>Relative lift</h3>
    <div class="num">{{ "%+.2f%%"|format(freq.relative_lift * 100) }}</div>
    <div>95% CI: {{ "%+.2f%% to %+.2f%%"|format(freq.ci95_relative[0]*100, freq.ci95_relative[1]*100) }}</div>
  </div>
  <div class="card">
    <h3>P(treatment &gt; control)</h3>
    <div class="num">{{ "%.1f%%"|format(bayes.prob_treatment_beats_control * 100) }}</div>
    <div>Bayesian posterior</div>
  </div>
</div>

<h2>Frequentist analysis</h2>
<table>
  <tr><th>Method</th><td>{{ freq.method }}</td></tr>
  <tr><th>Z-statistic</th><td>{{ "%.3f"|format(freq.z_statistic) }}</td></tr>
  <tr><th>P-value (two-sided)</th><td>{{ "%.4f"|format(freq.p_value_two_sided) }}</td></tr>
  <tr><th>P-value (one-sided)</th><td>{{ "%.4f"|format(freq.p_value_one_sided) }}</td></tr>
  <tr><th>Alpha</th><td>{{ freq.alpha }}</td></tr>
  <tr><th>Significant (two-sided)</th><td>{{ "Yes" if freq.significant_two_sided else "No" }}</td></tr>
  <tr><th>95% CI on absolute diff</th>
      <td>{{ "%+.4f to %+.4f"|format(freq.ci95_absolute[0], freq.ci95_absolute[1]) }}</td></tr>
</table>

<h2>Bayesian analysis</h2>
<table>
  <tr><th>Method</th><td>{{ bayes.method }}</td></tr>
  <tr><th>P(Treatment beats Control)</th>
      <td>{{ "%.2f%%"|format(bayes.prob_treatment_beats_control * 100) }}</td></tr>
  <tr><th>Expected absolute uplift</th>
      <td>{{ "%+.4f"|format(bayes.expected_uplift_absolute) }}</td></tr>
  <tr><th>Expected relative uplift</th>
      <td>{{ "%+.2f%%"|format(bayes.expected_uplift_relative * 100) }}</td></tr>
  <tr><th>95% credible interval (uplift)</th>
      <td>{{ "%+.4f to %+.4f"|format(bayes.credible_interval_uplift_abs[0], bayes.credible_interval_uplift_abs[1]) }}</td></tr>
  <tr><th>Expected loss if we ship treatment</th>
      <td>{{ "%.5f"|format(bayes.expected_loss_choosing_treatment) }}</td></tr>
  <tr><th>Expected loss if we keep control</th>
      <td>{{ "%.5f"|format(bayes.expected_loss_choosing_control) }}</td></tr>
  <tr><th>Monte Carlo samples</th><td>{{ bayes.samples_drawn }}</td></tr>
</table>

{% if revenue %}
<h2>Revenue impact</h2>
<table>
  <tr><th>RPV (control)</th><td>${{ "%.4f"|format(revenue.rpv_control) }}</td></tr>
  <tr><th>RPV (treatment)</th><td>${{ "%.4f"|format(revenue.rpv_treatment) }}</td></tr>
  <tr><th>RPV difference</th>
      <td>${{ "%+.4f"|format(revenue.rpv_diff) }}
          (95% CI ${{ "%+.4f"|format(revenue.rpv_diff_ci95[0]) }} to ${{ "%+.4f"|format(revenue.rpv_diff_ci95[1]) }})</td></tr>
  <tr><th>Annualized impact</th>
      <td>${{ "{:,.0f}"|format(revenue.annualized_impact) }}
          (range ${{ "{:,.0f}"|format(revenue.annualized_impact_low) }} to ${{ "{:,.0f}"|format(revenue.annualized_impact_high) }})</td></tr>
  <tr><th>AOV (control / treatment)</th>
      <td>${{ "%.2f"|format(revenue.aov_control) }} / ${{ "%.2f"|format(revenue.aov_treatment) }}</td></tr>
</table>
{% endif %}

{% if sequential %}
<h2>Sequential / peek-safe analysis</h2>
<table>
  <tr><th>Always-valid p-value</th><td>{{ "%.4f"|format(sequential.always_valid_p_value) }}</td></tr>
  <tr><th>Sequential decision</th><td><span class="pill">{{ sequential.decision }}</span></td></tr>
  <tr><th>Cumulative visitors</th><td>{{ sequential.cumulative_visitors }}</td></tr>
</table>
<p style="color:#666">Always-valid inference allows continuous monitoring of the experiment
without inflating Type-I error from naive "peeking."</p>
{% endif %}

<div class="footnote">
  Generated by ab-test-significance-toolkit v{{ tool_version }}. Methods: pooled two-proportion
  z-test, Beta-Binomial Monte Carlo, mSPRT always-valid sequential inference, delta-method revenue.
  This report is not a substitute for analyst judgment on practical significance, segmentation,
  or business context.
</div>
</body>
</html>
"""


def _classify_recommendation(freq_significant: bool, bayes_prob: float, sequential_decision: Optional[str]):
    """Translate the analysis triplet into a single CRO recommendation."""
    if sequential_decision == "ship" or (freq_significant and bayes_prob >= 0.95):
        return ("SHIP TREATMENT", "green", "Statistical evidence is strong from at least two methods. Roll out.")
    if bayes_prob >= 0.9 or freq_significant:
        return (
            "LEAN SHIP — VERIFY",
            "amber",
            "Evidence is suggestive but not unanimous. Confirm with a holdout or sequential peek.",
        )
    if sequential_decision == "no-effect-likely" or bayes_prob < 0.6:
        return ("KILL TREATMENT", "red", "Little evidence treatment beats control. Move on.")
    return ("KEEP TESTING", "amber", "Insufficient data. Continue running to reach the target sample size.")


def render_report(
    experiment_name: str,
    client_name: str,
    freq_result,
    bayes_result,
    revenue_result=None,
    sequential_result=None,
    tool_version: str = "0.2.0",
) -> str:
    """Render a full HTML report and return it as a string.

    Args:
        experiment_name: Display name of the experiment.
        client_name: Display name of the client / brand.
        freq_result: FrequentistResult instance.
        bayes_result: BayesianResult instance.
        revenue_result: Optional RevenueResult.
        sequential_result: Optional SequentialResult.
        tool_version: For footnote.

    Returns:
        Rendered HTML string.
    """
    env = Environment(
        loader=DictLoader({"report.html": REPORT_TEMPLATE}),
        autoescape=select_autoescape(["html"]),
    )

    recommendation, pill, summary = _classify_recommendation(
        freq_significant=freq_result.significant_two_sided,
        bayes_prob=bayes_result.prob_treatment_beats_control,
        sequential_decision=sequential_result.decision if sequential_result else None,
    )

    template = env.get_template("report.html")
    return template.render(
        experiment_name=experiment_name,
        client_name=client_name,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        freq=freq_result.to_dict(),
        bayes=bayes_result.to_dict(),
        revenue=revenue_result.to_dict() if revenue_result else None,
        sequential=asdict(sequential_result) if sequential_result else None,
        tool_version=tool_version,
        recommendation=recommendation,
        recommendation_pill=pill,
        recommendation_summary=summary,
    )


def write_report(html: str, path: str | Path) -> Path:
    """Write rendered HTML to disk and return the path."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html, encoding="utf-8")
    return p
