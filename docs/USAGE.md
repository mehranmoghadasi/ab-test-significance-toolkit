# Usage

## 1. Plan the test (sample size)

Before any experiment goes live, compute the per-variant sample size to detect
the smallest lift you would actually act on.

```bash
abtest sample-size --baseline 0.04 --mde 0.10 --power 0.8
# Required sample size per variant: 31,247
#   baseline=0.0400, mde=0.1 (relative), alpha=0.05, power=0.8
```

If a stakeholder insists on a smaller MDE, the calculator will surface the
true cost: the sample size grows quadratically as MDE shrinks.

## 2. Run the test, then analyze the GA4 export

Once the experiment is live, drop a GA4 export CSV with these columns:

| column | type | notes |
| --- | --- | --- |
| `experiment_variant` | string | e.g. `control`, `v1`, `v2` |
| `session_id` | string | de-duplication key |
| `converted` | 0/1 | event-level conversion flag |
| `revenue` | float | 0 for non-converters |

```bash
abtest analyze \
  --csv exports/experiment_42.csv \
  --control control \
  --treatment v1 \
  --client-name "Acme Co." \
  --experiment-name "Checkout CTA copy v1" \
  --annual-traffic 2400000 \
  --out reports/acme_v1.html
```

The output HTML is a single self-contained file — no JS, no external CSS. Email
it, attach it to a Notion page, or print it to PDF.

## 3. Continuous (peek-safe) monitoring

Pulling counts daily from the data warehouse? Use `peek` instead of running
`analyze` every day:

```bash
abtest peek \
  --c-visitors 14250 --c-conv 567 \
  --t-visitors 14180 --t-conv 671 \
  --tau-squared 1.0
```

This returns an always-valid p-value that does not inflate Type-I error when
queried repeatedly.

## 4. Programmatic API

```python
from ab_test_toolkit.frequentist import VariantSummary, two_proportion_z_test
from ab_test_toolkit.bayesian import analyze as bayes_analyze
from ab_test_toolkit.report import render_report, write_report

control = VariantSummary("control", 12500, 487)
treatment = VariantSummary("v1", 12500, 569)

freq = two_proportion_z_test(control, treatment)
bayes = bayes_analyze(
    control_conversions=control.conversions, control_visitors=control.visitors,
    treatment_conversions=treatment.conversions, treatment_visitors=treatment.visitors,
)

html = render_report(
    experiment_name="Checkout CTA copy v1",
    client_name="Acme Co.",
    freq_result=freq,
    bayes_result=bayes,
)
write_report(html, "out/report.html")
```

## Configuration

The toolkit reads no environment variables. Every input is explicit at the call
site so agency reports stay reproducible.
