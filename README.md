# SNT Benchmarks

Official benchmark and comparison repository for [SciNumTools3 (SNT3)](https://github.com/scinumtools/snt3). It currently compares Python physical-unit libraries and Python configuration parsers; further SNT3 comparisons can be added with their results summarized here.

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

### Reading these results

SNT3 has the lowest median in all 12 scalar cases and in 15 of 16 cases at each of 3 and 1,000 elements. At one million elements, the lowest medians are split across SNT3 (6 cases), Pint (3), unyt (4), and Astropy (3). These counts describe this run's ranks; small gaps may change in another run.

For million-element arrays, SNT3's compatible-unit addition takes **0.474 ms**, compared with **0.736 ms** for Pint, and its temperature conversion takes **0.247 ms**, compared with **0.414 ms** for unyt. Other operations favor different libraries: multiplication takes **0.202 ms** in Pint and **0.394 ms** in SNT3; division takes **0.408 ms** in unyt and **0.842 ms** in SNT3. The [full CSV](benchmarks/pyunits/results/reference-quick.csv) contains every case.

Array ownership affects what these timings measure. Attaching units to a million-element NumPy array takes **3.84 µs** in Pint and **270.75 µs** in SNT3; the CSV's `shares_input` check reports that Pint's result shares the input array while SNT3's does not. Same-unit conversion also differs sharply (**4.37 µs** for Pint versus **267.82 µs** for SNT3). The plain NumPy line in the figure provides numeric context without unit checks or quantity semantics. These single-process quick timings describe the pinned implementations on this machine; the pyperf workflow records repeated worker-process runs separately.

### Run Python units

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

## Python configuration parsing

The [parsing benchmark](benchmarks/pyserial/README.md) compares Python's `json.loads` and `tomllib.loads`, PyYAML's `safe_load`, and SNT3's `DIP.parse` on equivalent nested data. Every decoded result must exactly match the same Python mapping. The selected parameter counts, workload values, timing, output paths, and pinned versions live in [config.dip](benchmarks/pyserial/config.dip).

Run it with `./setup.sh --benchmark pyserial`; repeat `--size` or `--format` to select individual measurements. The first run creates its own pinned environment.

![Python JSON, YAML, TOML, and DIPL parsing times by parameter count and encoded size](benchmarks/pyserial/results/reference-quick.png)

Median decode times from the [full reference CSV](benchmarks/pyserial/results/reference-quick.csv), in milliseconds (lower is faster):

| Named parameters | JSON | TOML | YAML | DIPL |
| ---: | ---: | ---: | ---: | ---: |
| 10 | 0.003 | 0.042 | 0.427 | 0.439 |
| 100 | 0.015 | 0.280 | 2.768 | 3.203 |
| 1,000 | 0.149 | 2.705 | 26.184 | 37.404 |
| 10,000 | 1.575 | 27.009 | 266.844 | 1,181.677 |

JSON has the lowest median at every tested size in this run. YAML and DIPL are close at 10 parameters, while at 10,000 parameters DIPL takes **1.182 s** and YAML **0.267 s**. At that size, encoded documents range from **139 kB** for TOML to **239 kB** for DIPL; JSON is **219 kB** and YAML **169 kB**. The DIPL timing includes parsing into an evaluated parameter environment and extracting leaf values into the common Python mapping. These are measurements of the chosen **Python implementations and decode paths**, with different encoded document sizes; they do not establish an intrinsic speed ranking for the formats. The common workload does not exercise DIPL's units, constraints, or derived expressions.

This reference was recorded on **2026-10-24 19:37 UTC** on macOS arm64 with CPython 3.13.15, SNT3 0.9.8, and PyYAML 6.0.3. All **16/16** format-and-size checks passed. It used one process, two warmups, five timed samples, and a 10 ms calibration target. The 10,000-parameter DIPL case had an interquartile range of about **59 ms**, so repeat independent runs before treating small differences as stable. The [effective configuration](benchmarks/pyserial/results/reference-quick.config.json) records the settings and versions; [`./setup.sh --benchmark pyserial`](benchmarks/pyserial/README.md) reproduces the method with current machine timings.
