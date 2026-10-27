# Python configuration parsing

This benchmark compares four Python decode paths for the same nested `experiment` mapping: standard-library [`json.loads`](https://docs.python.org/3.13/library/json.html), [PyYAML](https://pyyaml.org/)'s `safe_load`, standard-library [`tomllib.loads`](https://docs.python.org/3.13/library/tomllib.html), and SNT3's [`DIP.parse`](https://github.com/scinumtools/snt3). Its method follows the shared-structure and equality-check pattern in [Canop's configuration deserializer benchmark](https://github.com/Canop/bench-config-deserializers); the data and Python parsers here are a separate comparison. The mapping contains a string, Boolean, integer, float, and a configurable number of named float parameters. All four decoders must reproduce the canonical Python mapping exactly before their timings are recorded.

The [DIPL settings](config.dip) govern the parameter counts, selected formats, experiment values, generated parameter names and values, timing, output paths, figure resolution, and pinned package versions. Project websites and method links are kept there as provenance. Python version and package pins are read from the DIP during environment setup; `benchmark.py` then uses `scinumtools3.dip.DIP` to read the selected configuration. Command-line options override selected settings for one run.

## Run

From the repository root:

```sh
./setup.sh --benchmark pyserial
./setup.sh --benchmark pyserial --size 10 --size 100 --format json --format dipl
./setup.sh --benchmark pyserial --measurement parser_only
./setup.sh --benchmark pyserial --samples 7 --target-ms 20
./setup.sh --benchmark pyserial --config path/to/custom.dip
./setup.sh --benchmark pyserial --source local
```

The first pinned run creates an isolated Python environment and installs the versions in `config.dip`. `--source local` uses the Python binding built in the configured local SNT3 checkout, with a separate environment and the same versions of the other benchmark packages. It requires that the binding already be built for the configured local Python interpreter. To compare pinned and local SNT3 on exactly the same interpreter, install the pinned SNT3 release into `.venv-local` and run the pinned mode with `--python benchmarks/pyserial/.venv-local/bin/python`. Each run writes a timestamped CSV, figure, and effective configuration snapshot to the configured results directory; automatic retention keeps the newest ten timestamped run sets. Local-source snapshots record the SNT3 commit, working-tree paths, and a hash of the tracked diff. Saved results retain Python and package versions and the OS family and CPU architecture, but omit hostnames, home-directory paths, and detailed OS build identifiers. The smallest generated document for each selected format is written to [`documents/`](documents/) when `execution.outputs.export_smallest` is true.

## What is measured

Document generation occurs before timing; each timed call decodes an in-memory string. The two figures compare these paths:

- **Parser output only:** each library returns its native result. JSON, YAML, and TOML return Python mappings. DIPL returns its parsed and evaluated environment without walking its nodes to build the benchmark's mapping.
- **Decode to common Python mapping:** each result is represented as the same nested mapping. JSON, YAML, and TOML already return that structure, so their measurements are the same parse call. DIPL additionally selects its evaluated leaf nodes and constructs the Python mapping.

“Parser output only” still includes DIPL's normal parsing, type handling, and evaluation; it does not time lexer or parser internals in isolation. Neither path includes document generation or disk I/O, and the suite does not exercise DIPL units, constraints, references, or derived expressions. Encoded byte counts remain in the CSV for context.

The default quick method uses two warmups and five samples per format and size, calibrating loops toward 10 ms per sample. A decode longer than the target is timed once per sample. Medians and interquartile ranges appear in the CSV. The [reference results](results/README.md) and figure are from one macOS arm64 process; they are an initial comparison, and measurements on other hardware or independent processes may differ.

## Reference figure and analysis

The reference figures use SNT3 0.9.12, Python 3.13.15, and the versions in [`config.dip`](config.dip). All 16 format/size combinations passed equality checks. At 10,000 parameters, parser-output medians were 1.56 ms for JSON, 27.28 ms for TOML, 266.07 ms for PyYAML `safe_load`, and 141.74 ms for DIPL. The 0.9.12 parser optimization reduces DIPL's parser-only median by about 59% versus the 0.9.11 snapshot; DIPL is now faster than YAML in this run, though remains about 5.2× slower than TOML. Quick results are single-process measurements; use repeated pyperf runs before making stable speed claims.

### Parser-output-only comparison

This is the single figure shown in the main README. It times each parser through its native result. DIPL still performs its normal parse, type handling, and evaluation, but the benchmark does not traverse the resulting nodes to create a second Python mapping.

![Parser-output-only times by parameter count for JSON, YAML, TOML, and DIPL](results/reference-quick.png)

### Decode-to-common-mapping comparison

The JSON, YAML, and TOML paths already return the common Python mapping, so their values match the parser-output-only figure. DIPL additionally selects evaluated leaf nodes and creates that mapping. At 10,000 parameters, this step raises DIPL's median from 141.74 ms to 160.55 ms (about 13.3%). It adds measurable conversion work, while parser-only DIPL remains slower than TOML and JSON in this workload.

The SNT3 0.9.12 release includes [DIP parsing optimizations](https://github.com/scinumtools/snt3/commit/5cac2a25910f4e89ec206921d7afde5323c447fc). In the matching 0.9.11-to-0.9.12 quick snapshots, the DIPL parser-only median fell by 85% at 10 parameters, 85% at 100, 81% at 1,000, and 59% at 10,000. This is one same-host quick run across two release versions; it shows the direction and size observed here, not a pyperf-level estimate of the optimization.

![Decode-to-common-mapping times by parameter count for JSON, YAML, TOML, and DIPL](results/reference-common-mapping.png)

The [full CSV](results/reference-quick.csv) and [effective configuration](results/reference-quick.config.json) contain the measurements and environment for this figure.

The results compare these selected implementations, not intrinsic format speeds. The pinned JSON decoder uses CPython's standard-library path; PyYAML uses `safe_load`; TOML uses `tomllib.loads`. DIPL parsing produces a typed, evaluated environment. Parser versions, document sizes, and native result models differ, so interpret the figures as an implementation comparison for this workload, not a universal ranking of JSON, YAML, TOML, and DIPL.
