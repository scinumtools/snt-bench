# Typed scientific configuration loading

This benchmark contrasts simple parsing with an end-to-end configuration task: loading equivalent scientific settings, checking types and constraints, applying a default, normalizing unit-bearing values, and evaluating derived values. It complements the [parser-only comparison](../pyserial/README.md), which measures data decoding without this extra model work.

## Participants

| Input | Timed implementation | Native behavior used |
|---|---|---|
| DIPL | SNT3 DIPL parser and evaluator | Typed declarations, value constraints, default value, references, expressions, and unit normalization are all expressed and evaluated in DIPL. |
| JSON | CPython `json` + Pydantic + Pint | JSON is decoded directly through Pydantic's JSON validation path; Pydantic supplies model constraints/defaults/computed fields, and Pint parses unit strings. |
| YAML | PyYAML `safe_load` + Pydantic + Pint | Safe YAML decoding plus typed model validation and unit parsing. |
| TOML | CPython `tomllib` + Pydantic + Pint | TOML decoding plus typed model validation and unit parsing. |

JSON, YAML, and TOML have no native typed model, constraint, default, or expression system corresponding to this workload, so Pydantic supplies that layer. Pint is used only to parse and normalize the unit-bearing inputs; DIPL uses its own unit support. CUE and Pkl have their own schema/configuration-language capabilities and are benchmarked with their native runtimes in [Schema and configuration validation](../schema-validation/README.md), rather than being wrapped in a Python dependency here.

The timed operation includes parsing the document and performing the participant's normal validation/default/derived-value work. Model class creation and document generation are outside timing. Inputs omit `label`, so the default is actually applied by each participant. Every result is converted to the same Python structure and checked before timing. A separate correctness check verifies rejection of five malformed inputs covering the name pattern, mode option, step bound, positive grid dimensions, and incompatible units. The timed workload includes unit-bearing timestep and grid spacing, and computes duration, grid cell count, and domain area.

The comparison does **not** include the cost of writing or maintaining Pydantic models. That code is part of the implementation, but not runtime. The Pydantic model is defined once and reused, while the DIPL schema declarations are in the input and parsed on each timed load. This represents repeated config loading with a predeclared Python model, not a matched cold-start comparison. It also does not claim that the formats have identical semantics: the task is an operational comparison of these pinned implementations for one shared scientific configuration.

## Run

```sh
./setup.sh --benchmark typed-config
./setup.sh --benchmark typed-config --source local
./setup.sh --benchmark typed-config --size 10 --size 100 --format dipl --format json
./setup.sh --benchmark typed-config --samples 9
```

[`config.dip`](config.dip) controls package pins, selected formats and sizes, every generated workload value, timing parameters, and output settings. Runs produce timestamped CSV, PNG, and effective-config files; only the ten newest timestamped runs are retained. Result metadata records software versions and coarse platform identifiers, without hostnames or absolute user paths.

The local-source option uses the binding in `../scinumtools3/build/python`, with the same pinned versions of the other packages. Its Python interpreter must match the extension ABI; the configured local interpreter is Python 3.14. The effective configuration snapshot records the local commit and a hash of tracked source changes. Since the pinned reference uses Python 3.13, compare local timings with care unless you also establish a pinned baseline on the local interpreter.

## Results

The reference figure is also shown in the repository [README](../../README.md#typed-configuration-loading). All participants produced the same normalized output and rejected the same five malformed cases. At 1,000 parameters, medians were 0.196 ms for JSON + Pydantic + Pint, 2.687 ms for TOML + Pydantic + Pint, 8.615 ms for DIPL, and 25.519 ms for YAML + Pydantic + Pint. DIPL is about 3.0× faster than the YAML stack in this run, while remaining slower than TOML and JSON. Relative to the 0.9.11 snapshot, the DIPL median fell by about 88%; the other implementations remained in roughly the same range. This aligns with the [DIP parsing optimizations in SNT3 0.9.12](https://github.com/scinumtools/snt3/commit/5cac2a25910f4e89ec206921d7afde5323c447fc), though the quick-run result is a single-machine measurement and should be confirmed with repeated runs before making a stable speed claim. The setup-scope difference above is one reason to treat these as workload evidence, not a general speed ranking.

The detailed [reference CSV](results/reference-quick.csv) contains per-format medians, interquartile ranges, payload sizes, pinned versions, and correctness status. The [effective configuration](results/reference-quick.config.json) records the run controls and workload values.

![Typed scientific configuration loading times for DIPL and JSON, YAML, and TOML with Pydantic](results/reference-quick.png)

Interpret the figure as the runtime cost of this complete workflow, not as a parser ranking. For results involving CUE/Pkl native models or broader validation cases, see the separate schema-validation benchmark linked above.

## Documentation and provenance

- [DIPL language documentation](https://github.com/scinumtools/snt3/blob/main/docs/source/dipl/index.rst): [types and units](https://github.com/scinumtools/snt3/blob/main/docs/source/dipl/index.rst#structured-typed-values), [references and expressions](https://github.com/scinumtools/snt3/blob/main/docs/source/dipl/index.rst#references-slices-and-templates), and [validation rules](https://github.com/scinumtools/snt3/blob/main/docs/source/dipl/index.rst#validation-metadata-and-provenance).
- [Pydantic models](https://pydantic.dev/docs/validation/latest/concepts/models/), [field constraints](https://pydantic.dev/docs/validation/latest/concepts/fields/), and [computed fields](https://pydantic.dev/docs/validation/latest/concepts/fields/#the-computed_field-decorator).
- [Pint quantities](https://pint.readthedocs.io/en/stable/user/defining-quantities.html).
- [CPython JSON](https://docs.python.org/3.13/library/json.html) and [TOML](https://docs.python.org/3.13/library/tomllib.html); [PyYAML safe loading](https://pyyaml.org/wiki/PyYAMLDocumentation).

Pinned package releases and their release URLs are listed in [`config.dip`](config.dip).
