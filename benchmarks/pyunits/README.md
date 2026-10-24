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

## Case IDs

The operation matrix case ID has four slash-separated parts:

```text
group/operation/input_kind/elements
```

`group` names the kind of work, `operation` names the specific operation, `input_kind` says whether the input is a scalar, Python list, or NumPy array, and `elements` is the number of values. Scalar cases always use `1`; array sizes come from `execution.selection.sizes` in [`config.dip`](config.dip). For example, `conversion/compound/ndarray/1000` converts a 1,000-element quantity from metres per second to kilometres per hour. `--list-cases` prints the IDs generated for the current configured sizes, and `--case` accepts shell-style glob patterns over the full ID (for example, `arithmetic/*/scalar/1`).

| `group` | `operation` values | What the operation does |
|---|---|---|
| `construction` | `attach_units` | Construct a quantity in metres from a scalar, Python list, or NumPy array. |
| `conversion` | `same` | Convert metres to metres. |
|  | `scaled` | Convert metres to millimetres. |
|  | `compound` | Convert metres per second to kilometres per hour. |
|  | `temperature` | Convert degrees Celsius to kelvin, using temperature-aware conversion where required. |
| `arithmetic` | `add_equal` | Add two metre quantities. |
|  | `add_compatible` | Add metres to an equivalent quantity in centimetres. |
|  | `subtract_equal` | Subtract one metre quantity from another. |
|  | `multiply` | Multiply metres by seconds, producing metre-seconds. |
|  | `divide` | Divide metres by seconds, producing metres per second. |
|  | `square` | Multiply a metre quantity by itself, producing square metres. |
|  | `sqrt` | Take the square root of a square-metre quantity, producing metres. |
| `numpy` | `np_add` | Add two metre quantities with `numpy.add`. |
|  | `np_sqrt` | Take the square root of a square-metre quantity with `numpy.sqrt`. |
|  | `np_sum` | Sum an array of metre quantities with `numpy.sum`. |

`input_kind` is `scalar` for one value; `list` is used only for list-based construction; `ndarray` is used for array construction, conversions, arithmetic, and NumPy operations. The separate `pyunits-basic` run is a macro workload rather than an operation-matrix case list: its records use `scalar/add_and_convert` (repeatedly add metre and US-foot quantities, then convert to US inches) and `array/construct_and_convert` (construct an array quantity in metres and convert it to millimetres).

## Feature support and benchmark coverage

This matrix follows the feature-comparison style of [SocialCompare's Python units table](https://socialcompare.com/en/comparison/python-units-quantities-packages), but records pinned releases and links to project documentation instead of time-varying popularity statistics. `✓` means the capability is described in the linked docs; `◐` means it depends on an optional integration or has a narrower/different meaning; `—` means the feature is unavailable in the compared API or the package documents a different model; `?` means I did not verify it in the cited docs. A `?` is not a claim that a feature is impossible. The SNT wheel is pinned at 0.9.8; because PUEL specifications are not versioned with that wheel, SNT links point to the immutable source snapshot [`ab0597d`](https://github.com/scinumtools/snt3/tree/ab0597d8c3a304a8282f2098e5af45a67e86ac0d). The other documentation links use the pinned versions from [`config.dip`](config.dip) where available.

| Feature | [SNT3 0.9.8](https://pypi.org/project/scinumtools3/0.9.8/) | [Pint 0.26.2](https://pint.readthedocs.io/en/0.26.2/) | [unyt 3.2.0](https://unyt.readthedocs.io/en/3.2.0/) | [Astropy 8.0.2](https://docs.astropy.org/en/8.0.2/) | [SymPy 1.14.0](https://docs.sympy.org/1.14.0/) | Tested in this suite |
|---|---|---|---|---|---|---|
| Built-in unit catalogs and unit systems | [✓ SI, CGS, English, and natural systems](https://github.com/scinumtools/snt3/blob/ab0597d8c3a304a8282f2098e5af45a67e86ac0d/docs/puel/tables/systems.md) | [✓ Unit registry](https://pint.readthedocs.io/en/0.26.2/getting/overview.html) | [✓ Built-in units and systems](https://unyt.readthedocs.io/en/3.2.0/usage.html) | [✓ Unit collections](https://docs.astropy.org/en/8.0.2/units/index.html) | [✓ Unit systems](https://docs.sympy.org/1.14.0/modules/physics/units/unitsystem.html) | Scalar construction and conversion |
| Built-in physical constants | [✓ Fixed and system-specific constants](https://github.com/scinumtools/snt3/blob/ab0597d8c3a304a8282f2098e5af45a67e86ac0d/docs/puel/tables/common.md#fixed-reference-constants) · [system-specific tables](https://github.com/scinumtools/snt3/blob/ab0597d8c3a304a8282f2098e5af45a67e86ac0d/docs/puel/tables/systems.md) | [✓](https://pint.readthedocs.io/en/0.26.2/getting/overview.html) | [✓](https://unyt.readthedocs.io/en/3.2.0/usage.html) | [✓](https://docs.astropy.org/en/8.0.2/constants/index.html) | [✓](https://docs.sympy.org/1.14.0/modules/physics/units/unitsystem.html) | No |
| User-defined units or unit systems | [✓ Host registration in PUQ; DIPL `$unit`](https://github.com/scinumtools/snt3/blob/ab0597d8c3a304a8282f2098e5af45a67e86ac0d/docs/dipl/syntax/units.md#custom-units) | [✓ Definitions and custom units](https://pint.readthedocs.io/en/0.26.2/advanced/defining.html) | [✓ User-defined units](https://unyt.readthedocs.io/en/3.2.0/usage.html#user-defined-units) | [✓ `def_unit`](https://docs.astropy.org/en/8.0.2/units/combining_and_defining.html#defining-units) | [✓ Extend unit systems](https://docs.sympy.org/1.14.0/modules/physics/units/unitsystem.html) | No |
| SI unit prefixes | [✓ Standard prefixes with per-unit permissions](https://github.com/scinumtools/snt3/blob/ab0597d8c3a304a8282f2098e5af45a67e86ac0d/docs/puel/tables/prefixes.md) | [✓](https://pint.readthedocs.io/en/0.26.2/user/defining-quantities.html) | [✓](https://unyt.readthedocs.io/en/3.2.0/usage.html) | [✓](https://docs.astropy.org/en/8.0.2/units/combining_and_defining.html) | [✓ SI and binary prefixes](https://docs.sympy.org/1.14.0/modules/physics/units/prefixes.html) | Yes, through scaled-unit cases |
| NumPy-backed quantities and array operations | [✓ PUEL array semantics](https://github.com/scinumtools/snt3/blob/ab0597d8c3a304a8282f2098e5af45a67e86ac0d/docs/puel/specification.md#numerical-arrays) · [Python/NumPy integration](https://github.com/scinumtools/snt3/blob/ab0597d8c3a304a8282f2098e5af45a67e86ac0d/docs/source/integrations/python.rst) | [✓](https://pint.readthedocs.io/en/0.26.2/user/numpy.html) | [✓ `unyt_array`](https://unyt.readthedocs.io/en/3.2.0/modules/unyt.array.html) | [✓ Quantity is an ndarray subclass](https://docs.astropy.org/en/8.0.2/units/quantity.html#numpy-functions) | [— Symbolic expressions, not NumPy-backed unit quantities](https://docs.sympy.org/1.14.0/modules/physics/units/index.html) | Yes for SNT, Pint, unyt, Astropy; SymPy is scalar-only |
| Conversion between compatible units | [✓](https://github.com/scinumtools/snt3/blob/ab0597d8c3a304a8282f2098e5af45a67e86ac0d/docs/source/modules/puq/conversion.rst) | [✓](https://pint.readthedocs.io/en/0.26.2/getting/tutorial.html#converting-to-different-units) | [✓](https://unyt.readthedocs.io/en/3.2.0/usage.html#unit-conversions-and-unit-systems) | [✓](https://docs.astropy.org/en/8.0.2/units/quantity.html#converting-to-different-units) | [✓](https://docs.sympy.org/1.14.0/modules/physics/units/quantities.html) | Yes, including scaled and compound conversions |
| Measurement uncertainties carried through unit arithmetic | [✓ Scalar, array, and per-element uncertainties; documented propagation model](https://github.com/scinumtools/snt3/blob/ab0597d8c3a304a8282f2098e5af45a67e86ac0d/docs/puel/sections/uncertainty.md) | [◐ Optional `uncertainties` integration](https://pint.readthedocs.io/en/0.26.2/getting/overview.html) | [?](https://unyt.readthedocs.io/en/3.2.0/usage.html) | [?](https://docs.astropy.org/en/8.0.2/units/quantity.html) | [— Symbolic variables are not measurement-uncertainty propagation](https://docs.sympy.org/1.14.0/modules/physics/units/index.html) | No |
| Non-float numeric magnitudes (for example, Decimal/Fraction) | [— Python binding stores scalar/array magnitudes as double/Float64; PUEL decimal literals are a separate feature](https://github.com/scinumtools/snt3/blob/ab0597d8c3a304a8282f2098e5af45a67e86ac0d/bindings/python/cpp/puq/bind_quantity.cpp) | [✓ Configurable numeric type](https://pint.readthedocs.io/en/0.26.2/getting/overview.html) | [◐ Integer and floating NumPy dtypes](https://unyt.readthedocs.io/en/3.2.0/usage.html#dealing-with-data-types) | [◐ NumPy dtype-based quantities](https://docs.astropy.org/en/8.0.2/units/quantity.html#the-numpy-dtype-of-a-quantity) | [◐ Exact/symbolic expressions](https://docs.sympy.org/1.14.0/modules/physics/units/quantities.html) | No |
| Logarithmic quantities and referenced levels such as dB/dBm | [✓ dB, Np, dBm/dBW; special conversion rules](https://github.com/scinumtools/snt3/blob/ab0597d8c3a304a8282f2098e5af45a67e86ac0d/docs/puel/sections/special-units.md#logarithmic-units) | [✓ Logarithmic units](https://pint.readthedocs.io/en/0.26.2/changes.html) | [?](https://unyt.readthedocs.io/en/3.2.0/usage.html) | [✓ Decibel and log units](https://docs.astropy.org/en/8.0.2/units/logarithmic.html) | [?](https://docs.sympy.org/1.14.0/modules/physics/units/index.html) | No |
| Offset temperatures and temperature differences | [✓ Celsius, Fahrenheit, Kelvin, Rankine; offset-aware conversion](https://github.com/scinumtools/snt3/blob/ab0597d8c3a304a8282f2098e5af45a67e86ac0d/docs/puel/sections/special-units.md#temperature-units) | [✓](https://pint.readthedocs.io/en/0.26.2/getting/overview.html) | [✓](https://unyt.readthedocs.io/en/3.2.0/usage.html#temperature-units) | [✓ Temperature equivalency](https://docs.astropy.org/en/8.0.2/units/equivalencies.html#temperature-equivalency) | [?](https://docs.sympy.org/1.14.0/modules/physics/units/index.html) | Yes for SNT, Pint, unyt, Astropy; not SymPy |
| String-based quantity parsing | [✓ PUEL expressions, including arrays, uncertainties, constants, and system selectors](https://github.com/scinumtools/snt3/blob/ab0597d8c3a304a8282f2098e5af45a67e86ac0d/docs/puel/specification.md#unit-expressions) | [✓](https://pint.readthedocs.io/en/0.26.2/getting/overview.html) | [✓](https://unyt.readthedocs.io/en/3.2.0/usage.html) | [✓](https://docs.astropy.org/en/8.0.2/units/quantity.html#creating-quantity-instances) | [— Python symbolic expressions](https://docs.sympy.org/1.14.0/modules/physics/units/index.html) | No |
| Named physical quantities and system scaling factors | [✓ Named quantity and scale-factor expressions](https://github.com/scinumtools/snt3/blob/ab0597d8c3a304a8282f2098e5af45a67e86ac0d/docs/puel/specification.md#named-entities) | [◐ Contexts define application-specific conversion rules](https://pint.readthedocs.io/en/0.26.2/user/contexts.html) | [?](https://unyt.readthedocs.io/en/3.2.0/usage.html) | [◐ Equivalencies define context-dependent conversions](https://docs.astropy.org/en/8.0.2/units/equivalencies.html) | [◐ Symbolic unit systems](https://docs.sympy.org/1.14.0/modules/physics/units/unitsystem.html) | No |

The PUEL specification defines fixed and system-specific constants, named physical quantities and conversion factors, host-registered custom units, unit prefixes, numerical arrays with per-element uncertainties, offset temperature conversions, and logarithmic units such as dB, Np, dBm, and dBW. The reference PUQ configuration enables the optional system, temperature, and logarithmic feature families by default.

These are package capabilities, not claims that the APIs or semantics are interchangeable. SNT's documented uncertainty model uses interval bounds for multiplication/division and first-order propagation for many math functions; it does not model correlations. Astropy temperature conversion uses an explicit equivalency, Pint's uncertainty integration is optional, and SymPy represents units symbolically rather than as NumPy-backed numerical quantities. The `Decimal`/`Fraction` row asks about Python numeric-type preservation: PUEL accepts decimal and scientific-notation literals, while the SNT Python binding currently constructs scalar magnitudes as `double` and arrays as `Float64`. The benchmark coverage column is deliberately narrower than the feature inventory: the timed cases exercise scalar/array construction, compatible conversion, arithmetic, and selected NumPy operations. They do not benchmark uncertainty propagation, logarithmic units, arbitrary numeric dtypes, or incompatible-operation diagnostics.

To rerun one measurement, pass one or more quoted `--case` globs and optional `--library` flags. `--size` replaces the configured array sizes; a case for that size must exist. For example:

```sh
./setup.sh --mode pyperf --case 'arithmetic/add_compatible/ndarray/1000' \
  --library snt --library pint --processes 5 --values 2
```

## Results and interpretation

![Reference quick-run medians for Python unit libraries by operation and input size](results/reference-quick.png)

The figure legend includes the library versions pinned for this reference run.

The figure shows median time per operation; the dotted NumPy trace is a unitless numeric baseline. See the [full results CSV](results/reference-quick.csv), [raw samples](results/reference-quick_samples.csv), and [effective configuration](results/reference-quick.config.json) for the measurements and environment.

In this reference quick run, SNT has the lowest median in all 12 scalar cases and in 15 of 16 cases at each of 3 and 1,000 elements. At one million elements, the lowest medians are split across SNT (6 cases), Pint (3), unyt (4), and Astropy (3). For example, SNT's million-element compatible-unit addition takes 0.474 ms, while its multiplication takes 0.394 ms compared with 0.202 ms for Pint. Array construction also differs in ownership: the CSV's `shares_input` field shows that Pint reuses the input buffer in this case, while SNT does not. Same-unit conversion medians are 4.37 µs for Pint and 267.82 µs for SNT. These are five samples from one process on one machine, so the rank counts describe this run and do not establish stable performance across systems.

Every matrix case has an equivalent plain NumPy operation as an unranked numeric baseline. Before timing a library case, the script checks value and shape against the expected result after conversion to the target unit. The basic comparison checks values and output units after timing. SNT, Pint, unyt, and Astropy run the matrix; SymPy participates only in the basic scalar workload. Operations start with preconstructed quantities; construction is measured separately.

Quick mode uses one process, configurable warmups and timed samples, and a short loop calibrated toward `quick.target_seconds`. It is useful for development feedback. Pyperf mode uses configurable worker processes, values, warmups, and minimum sample time. It stores raw `.pyperf.json`, a summary CSV, and a `_samples.csv` file. The summary reports median time, spread, rank within each case, and run environment. `--skip-memory` omits separate-process construction probes; otherwise `peak_rss_delta_bytes` is the increase in peak resident memory, which is only an approximate memory measure. NumPy input aliasing is reported for array construction.

Each run writes a CSV, sample CSV where applicable, figure, and effective configuration under `results/`. Automatic retention keeps the newest ten timestamped run sets in that directory; curated `reference-quick` files are exempt. Saved metadata retains useful comparison context such as Python and package versions, OS family, and CPU architecture, while removing hostnames, home-directory paths, boot time, and detailed OS build identifiers. [The main README](../../README.md) provides a compact results overview. A fresh complete pyperf run is needed before making a performance claim from repeated measurements. Compare runs only when hardware, Python, package versions, and workload settings match.

The [GitHub Actions pyperf workflow](../../.github/workflows/pyunits-pyperf.yml) runs the pinned matrix on `ubuntu-24.04` when dispatched manually. It uses the Python version, package pins, cases, sizes, libraries, timing settings, and output directory from `config.dip`; the workflow selects `--source pinned --mode pyperf`. Its job summary contains the measured median table, and its artifact holds the raw pyperf JSON, CSV files, figure, effective configuration, and a Markdown copy of the summary. GitHub runner timings should be compared only with runs on equivalent runner hardware and software.
