"""Command-line interface for the A/B test toolkit.

Usage:
    abtest analyze --csv exp.csv --control control --treatment v1 --out report.html
    abtest sample-size --baseline 0.04 --mde 0.10 --power 0.8
    abtest peek --c-visitors 5000 --c-conv 200 --t-visitors 5000 --t-conv 230
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from . import __version__
from .bayesian import analyze as bayes_analyze
from .frequentist import (
    two_proportion_z_test,
    required_sample_size_proportion,
    VariantSummary,
)
from .ga4_loader import load_ga4_csv, select_pair
from .report import render_report, write_report
from .revenue import revenue_per_visitor_delta
from .sequential import SequentialSnapshot, always_valid_p_value


console = Console()


@click.group(help="Agency-grade A/B test analyzer: Bayesian + Frequentist + Sequential.")
@click.version_option(__version__, prog_name="abtest")
def main():
    pass


@main.command("sample-size", help="Compute required per-variant sample size.")
@click.option("--baseline", type=float, required=True, help="Baseline conversion rate (0..1).")
@click.option("--mde", type=float, required=True, help="Minimum detectable effect (relative by default).")
@click.option("--alpha", type=float, default=0.05, show_default=True)
@click.option("--power", type=float, default=0.8, show_default=True)
@click.option("--absolute", is_flag=True, help="Treat MDE as absolute percentage points.")
def sample_size_cmd(baseline, mde, alpha, power, absolute):
    n = required_sample_size_proportion(
        baseline_rate=baseline,
        minimum_detectable_effect=mde,
        alpha=alpha,
        power=power,
        effect_is_relative=not absolute,
    )
    console.print(f"[bold]Required sample size per variant:[/bold] [green]{n:,}[/green]")
    console.print(
        f"  baseline={baseline:.4f}, mde={mde} ({'absolute' if absolute else 'relative'}), "
        f"alpha={alpha}, power={power}"
    )


@main.command("peek", help="Always-valid (peek-safe) inference for cumulative counts.")
@click.option("--c-visitors", type=int, required=True)
@click.option("--c-conv", type=int, required=True)
@click.option("--t-visitors", type=int, required=True)
@click.option("--t-conv", type=int, required=True)
@click.option("--tau-squared", type=float, default=1.0, show_default=True)
def peek_cmd(c_visitors, c_conv, t_visitors, t_conv, tau_squared):
    snap = SequentialSnapshot(
        visitors_control=c_visitors,
        conversions_control=c_conv,
        visitors_treatment=t_visitors,
        conversions_treatment=t_conv,
    )
    res = always_valid_p_value(snap, tau_squared=tau_squared)
    table = Table(title="Sequential analysis")
    table.add_column("metric")
    table.add_column("value")
    table.add_row("always-valid p-value", f"{res.always_valid_p_value:.4f}")
    table.add_row("decision", res.decision)
    table.add_row("z-statistic", f"{res.z_statistic:.3f}")
    table.add_row("cumulative visitors", f"{res.cumulative_visitors:,}")
    console.print(table)


@main.command("analyze", help="Run a full Bayesian + Frequentist + Revenue analysis on a GA4 CSV.")
@click.option("--csv", "csv_path", type=click.Path(exists=True), required=True)
@click.option("--control", "control_name", default="control", show_default=True)
@click.option("--treatment", "treatment_name", required=True)
@click.option("--out", "out_path", type=click.Path(), default="abtest_report.html", show_default=True)
@click.option("--client-name", default="Client", show_default=True)
@click.option("--experiment-name", default="Experiment", show_default=True)
@click.option("--annual-traffic", type=int, default=1_000_000, show_default=True,
              help="Annual traffic forecast for annualized revenue estimate.")
@click.option("--no-revenue", is_flag=True, help="Skip revenue analysis (use if rev column is unreliable).")
def analyze_cmd(csv_path, control_name, treatment_name, out_path, client_name,
                experiment_name, annual_traffic, no_revenue):
    exp = load_ga4_csv(csv_path, control_variant=control_name)
    control, treatment, c_rev, t_rev = select_pair(exp, control_name, treatment_name)

    freq = two_proportion_z_test(control, treatment)
    bayes = bayes_analyze(
        control_conversions=control.conversions,
        control_visitors=control.visitors,
        treatment_conversions=treatment.conversions,
        treatment_visitors=treatment.visitors,
    )

    revenue = None
    if not no_revenue and c_rev.size > 1 and t_rev.size > 1:
        revenue = revenue_per_visitor_delta(c_rev, t_rev, annual_traffic_forecast=annual_traffic)

    seq = always_valid_p_value(
        SequentialSnapshot(
            visitors_control=control.visitors,
            conversions_control=control.conversions,
            visitors_treatment=treatment.visitors,
            conversions_treatment=treatment.conversions,
        )
    )

    html = render_report(
        experiment_name=experiment_name,
        client_name=client_name,
        freq_result=freq,
        bayes_result=bayes,
        revenue_result=revenue,
        sequential_result=seq,
        tool_version=__version__,
    )
    written = write_report(html, out_path)
    console.print(f"[bold green]Report written:[/bold green] {written}")

    table = Table(title=f"Summary — {experiment_name}")
    table.add_column("metric")
    table.add_column("value")
    table.add_row("Control rate", f"{control.rate:.4%}")
    table.add_row("Treatment rate", f"{treatment.rate:.4%}")
    table.add_row("Relative lift", f"{freq.relative_lift:+.2%}")
    table.add_row("Freq. p-value (2-sided)", f"{freq.p_value_two_sided:.4f}")
    table.add_row("P(T > C) Bayesian", f"{bayes.prob_treatment_beats_control:.2%}")
    table.add_row("Always-valid p-value", f"{seq.always_valid_p_value:.4f}")
    table.add_row("Sequential decision", seq.decision)
    if revenue:
        table.add_row("RPV diff", f"${revenue.rpv_diff:+.4f}")
        table.add_row("Annualized impact", f"${revenue.annualized_impact:,.0f}")
    console.print(table)


@main.command("json", help="Run analyze and emit a JSON blob to stdout (no HTML).")
@click.option("--csv", "csv_path", type=click.Path(exists=True), required=True)
@click.option("--control", "control_name", default="control", show_default=True)
@click.option("--treatment", "treatment_name", required=True)
def json_cmd(csv_path, control_name, treatment_name):
    exp = load_ga4_csv(csv_path, control_variant=control_name)
    control, treatment, c_rev, t_rev = select_pair(exp, control_name, treatment_name)
    freq = two_proportion_z_test(control, treatment)
    bayes = bayes_analyze(
        control_conversions=control.conversions,
        control_visitors=control.visitors,
        treatment_conversions=treatment.conversions,
        treatment_visitors=treatment.visitors,
    )
    sys.stdout.write(json.dumps({
        "frequentist": freq.to_dict(),
        "bayesian": bayes.to_dict(),
    }, indent=2, default=str))
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
