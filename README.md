# ab-test-significance-toolkit

![license](https://img.shields.io/badge/license-MIT-blue) ![python](https://img.shields.io/badge/python-3.10%2B-blue) [![CI](https://github.com/mehranmoghadasi/ab-test-significance-toolkit/actions/workflows/python-app.yml/badge.svg)](https://github.com/mehranmoghadasi/ab-test-significance-toolkit/actions/workflows/python-app.yml) ![made-with](https://img.shields.io/badge/made%20with-scipy%20%2B%20jinja2-green)

> An agency-grade A/B test analyzer — Bayesian + Frequentist + Sequential significance, revenue uplift, GA4 export ingest, and exec-ready HTML reports in a single CLI.

```
Mockup — terminal + HTML report side-by-side (illustrative numbers)

┌──────────────────────────────────────────────┐   ┌────────────────────────────────────────┐
│ $ abtest analyze --csv exp.csv \             │   │  A/B Test Report: Checkout CTA copy v1  │
│        --treatment v1 --client "Acme Co."    │   │  ─────────────────────────────────    │
│                                              │   │  [ SHIP TREATMENT ]  Evidence is        │
│ Summary — Checkout CTA copy v1               │   │  strong from at least two methods.      │
│ ───────────────────────────────────        │   │                                         │
│  Control rate            3.96%               │   │  Control rate     3.96%                 │
│  Treatment rate          4.54%               │   │  Treatment rate   4.54%                 │
│  Relative lift          +14.65%              │   │  Relative lift   +14.65%                │
│  Freq p-value (2-sided)  0.0036              │   │  P(T > C)         97.4%                 │
│  P(T > C) Bayesian       97.4%               │   │                                         │
│  Always-valid p-value    0.0091              │   │  Annualized impact  +$248,400           │
│  Sequential decision     ship                │   │  ( range +$112,200 to +$384,600 )       │
│  RPV diff           +$0.1035                 │   │                                         │
│  Annualized impact  +$248,400                │   │  Always-valid p = 0.0091  | decision: ship
│ ───────────────────────────────────        │   │                                         │
│ Report written: reports/acme_v1.html         │   └────────────────────────────────────────┘
└──────────────────────────────────────────────┘
```

## The Problem

Most online A/B calculators stop at the question "is the conversion rate
difference significant?" — they ask for two numbers, return a p-value, and call
it a day. That isn't enough for an agency CRO program. Analysts routinely:

- run frequentist tests they peek at daily (inflating Type-I error),
- stop tests early on the first "significant" p-value,
- report only conversion-rate uplift, ignoring revenue and AOV,
- and rebuild client reports by hand every time.

Discussions in CRO communities ([CXL](https://cxl.com/ab-test-calculator/),
practitioner threads on `r/marketing` and `r/SEO`) flag these patterns repeatedly.
This toolkit is the consolidated workflow.

## The Solution

A single Python package + CLI that runs the whole analysis chain:

1. **Sample size up-front** — kill underpowered tests before they launch.
2. **Frequentist + Bayesian + Sequential** results in one pass.
3. **Revenue impact** in the same call, annualized at a forecast traffic level.
4. **Exec-ready HTML report** that an account manager can email without edits.

## Features

- Two-proportion z-test with both pooled & unpooled standard errors and 95% CIs.
- Bayesian Beta-Binomial posterior with `P(T>C)`, expected uplift, expected loss,
  and credible intervals via 100k-sample Monte Carlo.
- Always-valid p-values via the **mSPRT** construction so analysts can peek at
  the dashboard without inflating Type-I error.
- Welch t-test for continuous metrics (RPV, AOV, time-on-page).
- Sample-size calculator accepting either relative or absolute MDE.
- Revenue impact via delta method + bootstrap CI, annualized to a forecast traffic level.
- GA4 CSV loader with permissive column-mapping and de-dup of repeat sessions.
- Single self-contained HTML report — no external CSS/JS, prints clean to PDF.
- `click`-powered CLI + plain-old programmatic API.
- Type-hinted, tested with `pytest`, MIT-licensed.

## Architecture

```mermaid
flowchart LR
  A[GA4 export CSV] --> B[ga4_loader]
  B --> C[VariantSummary + revenue arrays]
  C --> D1[frequentist.z-test]
  C --> D2[bayesian.analyze]
  C --> D3[sequential.always-valid]
  C --> D4[revenue.RPV delta]
  D1 & D2 & D3 & D4 --> E[report.render_report]
  E --> F[Self-contained HTML]
  D1 & D2 --> G[CLI json mode]
```

Every analysis is a pure function of the input CSV — no DB, no server, no
hidden state. Each module is independently importable from Python.

## Tech Stack

- **Language**: Python 3.10+
- **Core**: `numpy`, `scipy`, `pandas`
- **CLI**: `click` + `rich`
- **Reports**: `jinja2` with embedded template
- **Tests**: `pytest`

## Installation

```bash
# from source
git clone https://github.com/mehranmoghadasi/ab-test-significance-toolkit.git
cd ab-test-significance-toolkit
pip install -e ".[dev]"

# verify
abtest --version
pytest
```

## Usage

```bash
# 1. plan a test
abtest sample-size --baseline 0.04 --mde 0.10 --power 0.8

# 2. peek-safe daily check
abtest peek --c-visitors 5000 --c-conv 200 --t-visitors 5000 --t-conv 230   # --tau 0.01 = prior SD of 1pp lift

# 3. full analysis + HTML report
abtest analyze \
  --csv examples/sample_ga4_export.csv \
  --treatment v1 \
  --client-name "Acme Co." \
  --experiment-name "Checkout CTA copy v1" \
  --annual-traffic 2400000 \
  --out reports/acme_v1.html
```

See [`docs/USAGE.md`](docs/USAGE.md) for the programmatic Python API.

## Sample Output

Real output from the bundled `examples/sample_ga4_export.csv` (3,000 sessions, 1,500 per arm — deliberately an *underpowered* test, because that is what most real peeks look like):

```
$ abtest analyze --csv examples/sample_ga4_export.csv --treatment v1 \
    --client-name "Demo Co" --experiment-name "Checkout CTA copy" --annual-traffic 500000

Report written: reports/demo.html
         Summary — Checkout CTA copy          
┏━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
┃ metric                  ┃ value            ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
│ Control rate            │ 3.9333%          │
│ Treatment rate          │ 5.2667%          │
│ Relative lift           │ +33.90%          │
│ Freq. p-value (2-sided) │ 0.0813           │
│ P(T > C) Bayesian       │ 95.94%           │
│ Always-valid p-value    │ 0.6312           │
│ Sequential decision     │ keep-collecting  │
│ RPV diff                │ $+0.9119         │
│ Annualized impact       │ $455,933         │
└─────────────────────────┴──────────────────┘
```

Read the three methods together: a frequentist p-value alone would tempt an early call, the Bayesian P(T > C) shows how far that is from certainty, and the always-valid p-value is the sequential test refusing to be fooled by 1,500 visitors per arm. The mockup at the top of this page shows what a *conclusive* run looks like.

## Roadmap

1. Multi-variant (k > 2) test mode with multiple-comparison correction.
2. CUPED variance reduction for pre-experiment covariates.
3. Server-side GA4 BigQuery export connector (skip the CSV step).
4. PDF export via `weasyprint` for one-command client deliverables.
5. White-label theming for agency-branded reports.
6. Stratified analysis by traffic source / device / geo.

## Project Structure

```
ab-test-significance-toolkit/
├── README.md
├── LICENSE
├── pyproject.toml
├── src/
│   └── ab_test_toolkit/
│       ├── __init__.py
│       ├── frequentist.py
│       ├── bayesian.py
│       ├── sequential.py
│       ├── revenue.py
│       ├── ga4_loader.py
│       ├── report.py
│       └── cli.py
├── tests/
│   ├── test_frequentist.py
│   ├── test_bayesian.py
│   └── test_sequential.py
├── ci/python-app.yml         # GitHub Actions workflow (also installed at .github/workflows/)
├── docs/
│   ├── ARCHITECTURE.md
│   ├── USAGE.md
│   └── screenshots/README.md
└── examples/
    └── sample_ga4_export.csv
```

## Contributing

Issues and PRs welcome. Please run `pytest` before sending changes — the test
suite covers the statistical correctness boundary that the rest of the toolkit
relies on.

## Changelog

- **0.3.0 (2026-09-19)** — **Sequential test rewritten.** The previous mSPRT implementation plugged the z-statistic into a formula that expects the raw mean difference and multiplied by n², so the exponent grew without bound: strong effects raised `OverflowError` (the repo's own test suite failed) and any moderate signal returned p≈0. The statistic is now computed from the effective sample size and per-observation variance, in the log domain, with a bounded exponent, and the prior is expressed as a lift SD (`--tau`, default 1 percentage point) instead of an unscaled `tau_squared=1.0`. Sequential decisions are now `ship` / `lean-ship` / `keep-collecting` — the old `no-effect-likely` label was wrong, because an always-valid p-value can only reject H0, never confirm a null. Also fixed the revenue block of the HTML report (Jinja `format` filter is printf-style, not `str.format`), replaced the 20-row sample with a 3,000-session dataset, and made the README's sample output a real run.
- **0.2.0** — Bayesian, frequentist, revenue and HTML report.

## License

[MIT](LICENSE) — use freely in commercial and agency work.

## About the Author

**Mehran Moghadasi** — Digital Marketing & Brand Manager (SEO · Google Ads · Meta Ads · Social Media), Calgary, AB.
[github.com/mehranmoghadasi](https://github.com/mehranmoghadasi) · [linkedin.com/in/mehranmoghadasi](https://www.linkedin.com/in/mehranmoghadasi)
