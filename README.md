# SNT Benchmarks

Official benchmark and comparison repository for [SciNumTools3 (SNT3)](https://github.com/scinumtools/snt3). It starts with Python physical units; comparisons of DIPL, YAML, TOML, JSON, and other SNT3 features can be added here with their results summarized in this README.

## Python physical units

The [pyunits benchmark](benchmarks/pyunits/README.md) compares [SNT3](https://github.com/scinumtools/snt3), [Pint](https://pint.readthedocs.io/en/stable/), [unyt](https://unyt.readthedocs.io/en/stable/), and [Astropy units](https://docs.astropy.org/en/stable/units/index.html). The separate scalar test also includes [SymPy units](https://docs.sympy.org/latest/modules/physics/units/). [NumPy](https://numpy.org/) is an unranked numeric baseline in the operation matrix. Project websites and pinned package versions are recorded in [config.dip](benchmarks/pyunits/config.dip).

![Python unit-library timings by operation and input size](benchmarks/pyunits/results/reference-quick.png)

Selected median times from the [full quick-run CSV](benchmarks/pyunits/results/reference-quick.csv), in microseconds per operation (lower is faster):

| Workload | SNT3 | Pint | unyt | Astropy |
| --- | ---: | ---: | ---: | ---: |
| Attach units to a scalar | 1.03 | 3.74 | 17.75 | 2.28 |
| Convert scalar metres to millimetres | 2.71 | 7.39 | 4.22 | 4.36 |
| Add compatible scalar units | 2.26 | 12.17 | 6.28 | 4.82 |
| Attach units to 1,000,000-element NumPy array | 270.75 | 3.84 | 17.04 | 289.29 |
| Add compatible units, 1,000,000 elements | 474.46 | 735.72 | 830.67 | 847.89 |

This reference was recorded on **2026-10-24 19:09 UTC** on macOS arm64 with Python 3.13.15, SNT3 0.9.8, Pint 0.26.2, unyt 3.2.0, and Astropy 8.0.2. All **240/240** library cases passed the configured value and shape checks. It used one process, two warmups, five timed samples per case, and sizes 3, 1,000, and 1,000,000; memory probes were skipped. These quick timings show a single development run and can change with machine load. The [sample CSV](benchmarks/pyunits/results/reference-quick_samples.csv) and [effective configuration](benchmarks/pyunits/results/reference-quick.config.json) are included for inspection. Use a full pyperf run for repeated worker-process measurements before drawing broader performance conclusions.

## Run a benchmark

```sh
./setup.sh                                      # full quick matrix, pinned releases
./setup.sh --mode pyperf                        # repeated pyperf matrix
./setup.sh --source local                       # built neighboring SNT3 checkout
./setup.sh --list-cases                         # show individual case IDs
./setup.sh --case 'conversion/scaled/scalar/1' --library snt --library pint
./setup.sh --benchmark pyunits-basic            # scalar/array comparison
./setup.sh --benchmark pyunits-basic --library snt --library sympy
```

The first run creates a virtual environment and installs versions from [config.dip](benchmarks/pyunits/config.dip). Each run produces a summary CSV, figure, and configuration snapshot under `benchmarks/pyunits/results/`; pyperf also saves raw JSON and per-sample CSV. Use `./setup.sh --help` for timing and selection flags. The [benchmark README](benchmarks/pyunits/README.md) explains the workloads, correctness checks, local-build setup, and result limits.

The [pyperf workflow](.github/workflows/pyunits-pyperf.yml) runs the pinned comparison on an Ubuntu GitHub runner on manual dispatch and monthly. Each run posts its measured table to the [Actions run summary](https://github.com/scinumtools/snt-bench/actions/workflows/pyunits-pyperf.yml) and uploads the CSV, raw samples, pyperf JSON, figure, effective configuration, and summary as one artifact. The table above remains the separately recorded quick-run reference; runner timings are identified by their own run date and environment.
