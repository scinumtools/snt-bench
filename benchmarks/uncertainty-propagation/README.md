# Uncertainty propagation

This benchmark compares propagated uncertainty values from SNT3, Pint, and MetroloPy
against first-order analytical calculations and reproducible Monte Carlo
propagation. It aims to expose behavior and semantics rather than rank packages
as interchangeable implementations. Inputs, operation cases, library pins,
Monte Carlo sample count and seed, interval coverage, tolerances, and output
settings are read from [`config.dip`](config.dip).

## Cases and interpretation

Inputs are independent normal distributions with configured nominal values and
standard deviations. Monte Carlo summaries use the fixed NumPy seed. Every row
records package-reported uncertainty, first-order analytical standard
deviation, Monte Carlo mean and standard deviation, the configured central
Monte Carlo interval, coverage of the package-reported `estimate ± uncertainty`
interval, and whether Monte Carlo spread agrees with the analytical result
within the configured sampling tolerance.

| Case ID | Model and purpose |
|---|---|
| `linear_conversion` | Convert an uncertain Celsius temperature point to Fahrenheit; checks offset conversion and uncertainty scaling. |
| `addition` | Add independent metre quantities; contrasts quadrature standard deviation with SNT's conservative absolute-uncertainty sum. |
| `product` | Multiply independent metre and second quantities; contrasts first-order standard uncertainty with SNT's interval bound. |
| `reciprocal` | Propagate uncertainty through `1/x`; compares derivative approximation with the Monte Carlo distribution. |

Analytical standard deviations follow the [GUM first-order law of propagation](https://doi.org/10.59161/JCGM100-2008E).
The [2026 GUM amendment on nonlinearity](https://doi.org/10.59161/PPDI3267)
is relevant to the reciprocal case. The sampling check follows the role of
[JCGM 101:2008](https://doi.org/10.59161/JCGM101-2008), which describes
propagation of distributions using a Monte Carlo method.

SNT stores absolute uncertainty in the quantity's unit. Its documented
addition/subtraction rule sums absolute uncertainties; multiplication/division
use interval extrema, and selected math functions use first-order derivatives.
These interval bounds are not one-sigma estimates. Pint's uncertainty
integration is optional and uses the [`uncertainties` package](https://pint.readthedocs.io/en/0.26.2/getting/overview.html),
which reports standard deviations propagated through first-order derivatives.
MetroloPy's [`gummy` quantities](https://nrc-cnrc.github.io/MetroloPy/_build/html/metrolopy.html)
carry units and standard uncertainties and propagate them using first-order
uncertainty calculus. This suite checks independent inputs only, so MetroloPy's
correlation support is not exercised here.
The plot therefore places each reported uncertainty beside Monte Carlo
standard deviation, while the CSV identifies the model for each row. A wider
SNT bound is not labeled a worse standard deviation. The benchmark models
independent inputs and does not exercise correlation handling in Pint or
MetroloPy.

## Results

![Reported uncertainty relative to Monte Carlo standard deviation](results/reference-quick.png)

The vertical reference at `1` is the Monte Carlo standard deviation for each
case. Pint and MetroloPy first-order uncertainties agree closely with it in all
four cases.
SNT matches Pint for the linear conversion, while its addition and product
intervals are wider by design; in the reciprocal case its bound is modestly
wider than the first-order estimate. All four Monte Carlo standard deviations
are within 0.7% of the analytical values in this run. The CSV's `mc_coverage`
column further shows how often each reported symmetric interval covers the
Monte Carlo draws.

For the independent-addition case, the analytical standard deviation is
`sqrt(0.2² + 0.3²) ≈ 0.361 m`; SNT reports the conservative bound `0.5 m`, while
Pint and MetroloPy report `0.361 m`. For the product case, the first-order standard
deviation is approximately `3.105 m·s`, and SNT reports an interval bound of
`3.86 m·s`. The [CSV](results/reference-quick.csv) contains Monte Carlo
statistics and coverage. The [run snapshot](results/reference-quick.config.json)
records the pinned versions and config hash.

This is an illustrative suite, not a metrological validation campaign. Normal
independent inputs and a few smooth models do not cover correlated quantities,
non-normal distributions, discontinuities, heavy-tailed inputs, or all
nonlinear regimes. For publication, report the exact configuration and software
versions and extend cases to the measurement model and input distributions
relevant to the scientific use.

## Running

```sh
./setup.sh --benchmark uncertainty-propagation --quick
```

Select operations with repeatable `--case GLOB` arguments, participants with
`--library snt|pint|metrolopy`, and sample count with `--samples N`. Pass `--python PATH`
to use an existing environment. `--quick` refreshes the tracked reference
snapshot. New runs create timestamped files; retention removes result groups
older than the newest ten.

## References

- JCGM, [JCGM 100:2008, Guide to the Expression of Uncertainty in Measurement](https://doi.org/10.59161/JCGM100-2008E).
- JCGM, [Amendment 1:2026, Nonlinearity in Measurement Models](https://doi.org/10.59161/PPDI3267).
- JCGM, [JCGM 101:2008, Propagation of Distributions Using a Monte Carlo Method](https://doi.org/10.59161/JCGM101-2008).
- SciNumTools3, [PUQ uncertainty propagation specification](https://github.com/scinumtools/snt3/blob/ab0597d8c3a304a8282f2098e5af45a67e86ac0d/docs/puel/sections/uncertainty.md).
- MetroloPy, [version 1.1.1 release](https://pypi.org/project/metrolopy/1.1.1/) and [documentation](https://nrc-cnrc.github.io/MetroloPy/_build/html/metrolopy.html).
