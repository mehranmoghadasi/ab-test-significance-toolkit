# Screenshots

The HTML reports rendered by this toolkit are designed to be screenshotted or
printed to PDF and dropped into a Notion page or an email. Below is a textual
description of what the rendered report looks like — actual screenshots will be
attached to the GitHub release notes once the v1.0 milestone ships.

## "Headline" panel (top of the report)

A bold blue band runs across the top of the page reading **"A/B Test Report:
Checkout CTA copy v1"**. Underneath sits a single colored pill labelled
**SHIP TREATMENT** in green, **LEAN SHIP — VERIFY** in amber, **KILL TREATMENT**
in red, or **KEEP TESTING** in amber. The recommendation block sits to the
right of the pill with a one-sentence justification.

## Four KPI cards (2×2 grid)

Each card is a thin grey-bordered rectangle with a small label and a large
number:

- Control conversion rate (e.g. **3.96%**)
- Treatment conversion rate (e.g. **4.54%**)
- Relative lift (e.g. **+14.65%** with the 95% CI below it)
- P(treatment beats control) (e.g. **97.4%** with "Bayesian posterior" below)

## Three labelled tables

The remainder of the page is three tables on a white background with
alternating-row light-grey headers:

1. **Frequentist analysis** — z-statistic, two-sided & one-sided p-values, alpha,
   significance flags, and the 95% CI on absolute difference.
2. **Bayesian analysis** — `P(T>C)`, expected absolute & relative uplift, the 95%
   credible interval, expected loss for each decision, and the Monte Carlo sample
   count.
3. **Revenue impact** (optional) — RPV for each variant, RPV difference with CI,
   annualized impact at the forecast traffic level, and per-converter AOV.

## "Sequential / peek-safe analysis" footer panel

A small final table with the always-valid p-value, the sequential decision pill,
and cumulative visitors. A short paragraph below it explains why the
"always-valid" framing matters when stakeholders peek at the dashboard daily.

## Footer

A muted grey caveat block at the bottom: tool version, summary of methods used,
and a note that the report supplements but does not replace analyst judgment on
practical significance, segmentation, and business context.
