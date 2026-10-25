# Uncertainty propagation

This benchmark compares propagated uncertainty values from SNT3, Pint, and MetroloPy
against closed-form references and seeded Monte Carlo propagation. It reports
uncertainty spread, nominal-value bias, and coverage of each reported
estimate ± uncertainty interval. Inputs, cases, library pins, sample count and
seed, coverage targets, tolerances, and output settings are read from
[`config.dip`](config.dip).

## Cases and interpretation

Monte Carlo summaries use the fixed NumPy seed. Most inputs are normal; the
rectangular case uses a uniform input and the correlation case uses a bivariate
normal. Each row records the package result and uncertainty, closed-form
reference standard deviation, Monte Carlo mean and standard deviation, central
95% Monte Carlo interval, and observed coverage of the reported
`estimate ± uncertainty` interval. Error columns show uncertainty error versus
Monte Carlo spread, nominal-value difference from the Monte Carlo mean, and
coverage relative to the normal one-standard-deviation reference (68.27%).

| Case ID | Model and purpose |
|---|---|
| `linear_conversion` | Convert an uncertain Celsius temperature point to Fahrenheit; checks offset conversion and uncertainty scaling. |
| `addition` | Add independent normal metre quantities; checks root-sum-square uncertainty propagation. |
| `product` | Multiply independent normal metre and second quantities; compares propagated uncertainty with the exact product-distribution standard deviation. |
| `reciprocal` | Propagate uncertainty through `1/x`; compares first-order propagation with Monte Carlo. The normal input is centered 40 standard deviations from zero. |
| `square_nonlinear` | Square a normal input with a large relative uncertainty; compares first-order output uncertainty and nominal value with the exact output moments and Monte Carlo. |
| `correlated_addition` | Add normal metre quantities with correlation `ρ = 0.8`; checks covariance propagation. SNT3 0.9.10 propagates the configured correlation through source-aware first-order sensitivities. |
| `rectangular_linear` | Compare a uniform Monte Carlo input with library inputs carrying the same mean and standard deviation; shows how a one-standard-deviation interval's coverage depends on distribution shape. |

First-order references follow the [GUM law of propagation](https://doi.org/10.59161/JCGM100-2008E).
The product and square cases use exact output moments for their configured
Gaussian inputs. The [2026 GUM amendment on nonlinearity](https://doi.org/10.59161/PPDI3267)
is relevant to the nonlinear cases. The sampling check follows the role of
[JCGM 101:2008](https://doi.org/10.59161/JCGM101-2008), which describes
propagation of distributions using a Monte Carlo method.

Pint uses the [`uncertainties` package](https://pint.readthedocs.io/en/0.26.2/getting/overview.html)
for first-order standard uncertainty propagation; its correlation construction
is documented by [`uncertainties`](https://uncertainties.readthedocs.io/en/latest/user_guide.html#use-of-a-correlation-matrix).
MetroloPy's
[`gummy` quantities](https://nrc-cnrc.github.io/MetroloPy/_build/html/metrolopy.html)
support first-order propagation, correlated inputs, and distribution objects.
For the rectangular case, each package receives the same nominal value and
standard deviation; the uniform distribution is used only for the Monte Carlo
reference, so this case measures propagation behavior and interval coverage,
not native non-normal-distribution support.
SNT3 0.9.10 uses source-aware first-order propagation and represents input correlations through shared uncertainty sources. This behavior is documented in the [implementation change](https://github.com/scinumtools/snt3/commit/c82b6c97). The
reported interval coverage is descriptive: a uniform distribution does not
have the normal 68.27% coverage within ±1 standard deviation.

## Results

![Uncertainty ratio and observed coverage with Monte Carlo confidence intervals](results/reference-quick.png)

The upper panel shows reported uncertainty divided by Monte Carlo standard
deviation; the horizontal reference at `1` indicates equal spread. The lower
panel shows the observed coverage percentage of each reported ±uncertainty
interval, with 95% Wilson confidence intervals for Monte Carlo sampling and a
68.27% normal one-sigma reference line. In this pinned SNT3 0.9.10 run, addition, product, reciprocal, and linear conversion agree with the first-order comparison participants. For correlated addition, SNT, Pint, and MetroloPy report 0.475395 against a Monte Carlo standard deviation of 0.476318. The nonlinear square case reports first-order uncertainty 0.4 while Monte Carlo spread is about 0.4558 and the Monte Carlo mean differs from the nominal square, illustrating the limits of first-order propagation for this deliberately nonlinear input.
For the uniform input, all participants report the input standard deviation,
but the interval covers about 57.6% of draws, as expected for a uniform
distribution rather than a normal one. The correlation case agrees with the
closed-form reference across all three packages.

The [CSV](results/reference-quick.csv) includes signed and relative errors,
coverage, and Monte Carlo reference checks. The
[run snapshot](results/reference-quick.config.json) records the pinned versions
and configuration hash.

This is an illustrative suite, not a metrological validation campaign. It does
not cover discontinuities, heavy-tailed inputs, or all nonlinear regimes. For
publication, report the exact configuration and software versions and extend
cases to the measurement model and input distributions relevant to the
scientific use.

## Running

```sh
./setup.sh --benchmark uncertainty-propagation --quick
```

To benchmark the neighboring `../scinumtools3` checkout, use:

```sh
./setup.sh --benchmark uncertainty-propagation --source local
```

Local mode uses the Python interpreter and built extension from that checkout,
then creates a separate `.venv-local` for the pinned comparison dependencies.
The local extension must be built for the configured interpreter ABI. Its
results are timestamped and do not replace the tracked pinned reference.

Select operations with repeatable `--case GLOB` arguments, participants with
`--library snt|pint|metrolopy`, and sample count with `--samples N`. Pass `--python PATH`
to use an existing environment. `--quick` refreshes the tracked reference
snapshot for pinned runs. New runs create timestamped files; retention removes
result groups older than the newest ten.

## References

- JCGM, [JCGM 100:2008, Guide to the Expression of Uncertainty in Measurement](https://doi.org/10.59161/JCGM100-2008E).
- JCGM, [Amendment 1:2026, Nonlinearity in Measurement Models](https://doi.org/10.59161/PPDI3267).
- JCGM, [JCGM 101:2008, Propagation of Distributions Using a Monte Carlo Method](https://doi.org/10.59161/JCGM101-2008).
- SciNumTools3, [PUQ uncertainty propagation specification](https://github.com/scinumtools/snt3/blob/ab0597d8c3a304a8282f2098e5af45a67e86ac0d/docs/puel/sections/uncertainty.md).
- MetroloPy, [version 1.1.1 release](https://pypi.org/project/metrolopy/1.1.1/) and [documentation](https://nrc-cnrc.github.io/MetroloPy/_build/html/metrolopy.html).
