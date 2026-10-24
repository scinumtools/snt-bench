# SNT Benchmarks

Official benchmark and comparison repository for [SciNumTools3 (SNT3)](https://github.com/scinumtools/snt3).

## Benchmarks

- [Python physical units](benchmarks/pyunits/README.md)
- [Python configuration parsing](benchmarks/pyserial/README.md)

## Python physical units

Comparison of SNT3, Pint, unyt, and Astropy unit operations across scalar and array sizes. The figure shows median time per operation; NumPy is included as a unitless baseline.

The workload categories are informed by [Goldbaum et al.'s unit-library benchmark (2018)](https://doi.org/10.21105/joss.00809).

[Methods, full results, and run instructions](benchmarks/pyunits/README.md).

![Python unit-library timings by operation and input size](benchmarks/pyunits/results/reference-quick.png)

## Python configuration parsing

Comparison of JSON, YAML, TOML, and DIPL parsing for equivalent nested data. The figure shows median decode time by parameter count and encoded document size.

The method follows the equivalent-structure and equality-check pattern in [Canop's configuration deserializer benchmark](https://github.com/Canop/bench-config-deserializers).

[Methods, full results, and run instructions](benchmarks/pyserial/README.md).

![Python JSON, YAML, TOML, and DIPL parsing times by parameter count and encoded size](benchmarks/pyserial/results/reference-quick.png)
