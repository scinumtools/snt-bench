# Python unit-library comparison

The suite has two comparisons. `compare.py` measures scalar add-and-convert and 100,000-element array construction-and-conversion workloads, using the reference expression from [SNT3 revision `2e7fde7`](https://github.com/scinumtools/snt3/tree/2e7fde7c8e38d6224c620190e1a5848c2588da04). `matrix.py` covers quantity construction, unit conversion, arithmetic, and NumPy calls across scalar, short-array, and large-array inputs. The matrix categories follow the approach of [Goldbaum et al. (2018)](https://doi.org/10.21105/joss.00809), which benchmarks applying units to data, arithmetic, NumPy operations, and increasing input sizes. This suite uses its own workloads and pinned library versions; it is not a reproduction of that study. The tested operations and units are defined in the scripts so that each library performs equivalent work.

## Run

From this repository's root:

```sh
./setup.sh                                      # pinned SNT3, quick full matrix
./setup.sh --mode pyperf                        # repeated worker-process run
./setup.sh --source local --mode quick          # neighboring SNT3 checkout
./setup.sh --list-cases                         # IDs available for reruns
./setup.sh --case 'conversion/scaled/scalar/1' --library snt --library pint
./setup.sh --benchmark pyunits-basic            # scalar/array comparison
./setup.sh --benchmark pyunits-basic --library snt --library sympy
```

The runner creates `.venv-pinned` or `.venv-local` in this directory on first use and installs the versions from [config.dip](config.dip). Pinned mode uses Python 3.13 by default. Local mode expects a built binding in `../scinumtools3/build/python/scinumtools3` and creates its environment from that checkout's `.venv/bin/python`, so the extension ABI matches. Set `SNT_LOCAL_REPO` for another checkout. Use `--python PATH` or `PYTHON=PATH` to use an already prepared environment; the runner checks its versions and does not install into it.

Edit [config.dip](config.dip) to change the source, timing mode, array sizes, selected cases and libraries, input values, correctness tolerances, quick timing controls, pyperf controls, scalar/array workload controls, and pinned versions. `execution.selection.libraries` controls the matrix; `execution.selection.basic_libraries` controls the basic comparison. Command-line flags override the corresponding settings for one run. Changing a version in the DIP file changes the environment created by the runner. `pyunits.execution.paths` controls interpreter and output locations. Package websites and the reference revision are provenance fields recorded with results; they do not alter measurements. Every value has a DIPL description. The runner writes an effective `.config.json` with the DIP file hash, overrides, versions, websites, and command next to every completed run.

`compare.py` and `matrix.py` also read their defaults from the selected DIP file when invoked directly with `--config PATH`. Their command-line values override the DIP. The memory probe receives the matrix input range explicitly.

To rerun one measurement, pass one or more quoted `--case` globs and optional `--library` flags. `--size` replaces the configured array sizes; a case for that size must exist. For example:

```sh
./setup.sh --mode pyperf --case 'arithmetic/add_compatible/ndarray/1000' \
  --library snt --library pint --processes 5 --values 2
```

## Results and interpretation

![Reference quick-run medians for Python unit libraries by operation and input size](results/reference-quick.png)

The figure shows median time per operation; the dotted NumPy trace is a unitless numeric baseline. See the [full results CSV](results/reference-quick.csv), [raw samples](results/reference-quick_samples.csv), and [effective configuration](results/reference-quick.config.json) for the measurements and environment.

In this reference quick run, SNT has the lowest median in all 12 scalar cases and in 15 of 16 cases at each of 3 and 1,000 elements. At one million elements, the lowest medians are split across SNT (6 cases), Pint (3), unyt (4), and Astropy (3). For example, SNT's million-element compatible-unit addition takes 0.474 ms, while its multiplication takes 0.394 ms compared with 0.202 ms for Pint. Array construction also differs in ownership: the CSV's `shares_input` field shows that Pint reuses the input buffer in this case, while SNT does not. Same-unit conversion medians are 4.37 µs for Pint and 267.82 µs for SNT. These are five samples from one process on one machine, so the rank counts describe this run and do not establish stable performance across systems.

Every matrix case has an equivalent plain NumPy operation as an unranked numeric baseline. Before timing a library case, the script checks value and shape against the expected result after conversion to the target unit. The basic comparison checks values and output units after timing. SNT, Pint, unyt, and Astropy run the matrix; SymPy participates only in the basic scalar workload. Operations start with preconstructed quantities; construction is measured separately.

Quick mode uses one process, configurable warmups and timed samples, and a short loop calibrated toward `quick.target_seconds`. It is useful for development feedback. Pyperf mode uses configurable worker processes, values, warmups, and minimum sample time. It stores raw `.pyperf.json`, a summary CSV, and a `_samples.csv` file. The summary reports median time, spread, rank within each case, and run environment. `--skip-memory` omits separate-process construction probes; otherwise `peak_rss_delta_bytes` is the increase in peak resident memory, which is only an approximate memory measure. NumPy input aliasing is reported for array construction.

Each run writes a CSV, sample CSV where applicable, figure, and effective configuration under `results/`. [The main README](../../README.md) provides a compact results overview. A fresh complete pyperf run is needed before making a performance claim from repeated measurements. Compare runs only when hardware, Python, package versions, and workload settings match.

The [GitHub Actions pyperf workflow](../../.github/workflows/pyunits-pyperf.yml) runs the pinned matrix on `ubuntu-24.04` when dispatched manually and on the first day of each month. It uses the Python version, package pins, cases, sizes, libraries, timing settings, and output directory from `config.dip`; the workflow selects `--source pinned --mode pyperf`. Its job summary contains the measured median table, and its artifact holds the raw pyperf JSON, CSV files, figure, effective configuration, and a Markdown copy of the summary. GitHub runner timings should be compared only with runs on equivalent runner hardware and software.
