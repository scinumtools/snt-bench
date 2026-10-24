# SNT Benchmarks

Official benchmark and comparison repository for [SciNumTools3 (SNT3)](https://github.com/scinumtools/snt3).

## Benchmarks

- [Python physical units](benchmarks/pyunits/README.md)
- [Python configuration parsing](benchmarks/pyserial/README.md)
- [Schema and configuration validation](benchmarks/schema-validation/README.md)

## Python physical units

Comparison of SNT3, Pint, unyt, and Astropy unit operations across scalar and array sizes. The figure shows median time per operation, with pinned library versions in the legend; NumPy is included as a unitless baseline.

The workload categories are informed by [Goldbaum et al.'s unit-library benchmark (2018)](https://doi.org/10.21105/joss.00809).

[Methods, full results, and run instructions](benchmarks/pyunits/README.md).

![Python unit-library timings by operation and input size](benchmarks/pyunits/results/reference-quick.png)

## Python configuration parsing

Comparison of JSON, YAML, TOML, and DIPL parsing for equivalent nested data. The figure shows median decode time by parameter count and encoded document size, with parser versions in the legend.

The method follows the equivalent-structure and equality-check pattern in [Canop's configuration deserializer benchmark](https://github.com/Canop/bench-config-deserializers).

[Methods, full results, and run instructions](benchmarks/pyserial/README.md).

![Python JSON, YAML, TOML, and DIPL parsing times by parameter count and encoded size](benchmarks/pyserial/results/reference-quick.png)

## Schema and configuration validation

Feature support and command-line validation timing comparison for DIPL, JSON Schema, CUE, and Pkl, with each capability linked to primary project documentation. All four participants pass the shared eight-case correctness check; the figure compares same-size-per-class native CLI batches over 20 repetitions.

[Feature matrix, methods, analysis, and full results](benchmarks/schema-validation/README.md).

![Schema validation native CLI batch timings for DIPL, JSON Schema, CUE, and Pkl](benchmarks/schema-validation/results/schema_validation_20261024T205728Z.png)
