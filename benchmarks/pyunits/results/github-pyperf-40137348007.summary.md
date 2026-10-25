# Python units: pyperf comparison

Profile: CI representative subset; it is a shorter screening run, not the exhaustive matrix.
Run: 2026-10-24T22:10:50+00:00 on Linux-x86_64 (x86_64); Python 3.13.16.
Checks: **60/60 PASS** across 15 cases.
Measurement: 3 processes, 3 values and 1 warmups per process; minimum 0.02 s per value.
Sizes: 3, 1000, 1000000. Packages: snt 0.9.8, pint 0.26.2, unyt 3.2.0, astropy 8.0.2, numpy 2.5.4.
Configuration SHA-256: `77c56ed3d652eb4bc4dc432ad8be044b78271ba94ce4b25d84a158ffb82f195f`.

Median microseconds per operation; lower is faster. NumPy is an unranked numeric baseline.

| Case | NumPy | snt | pint | unyt | astropy |
| --- | ---: | ---: | ---: | ---: | ---: |
| `construction/attach_units/scalar/1` | 0.429 | 1.893 | 7.941 | 53.177 | 4.758 |
| `construction/attach_units/ndarray/1000` | 0.199 | 3.115 | 7.974 | 48.316 | 5.096 |
| `construction/attach_units/ndarray/1000000` | 0.199 | 206.568 | 7.986 | 48.860 | 212.423 |
| `conversion/scaled/scalar/1` | 0.072 | 4.976 | 16.333 | 9.759 | 10.034 |
| `arithmetic/add_compatible/scalar/1` | 1.174 | 3.939 | 26.123 | 14.774 | 11.437 |
| `conversion/scaled/ndarray/1000` | 1.515 | 6.146 | 19.941 | 9.806 | 10.173 |
| `conversion/compound/ndarray/1000` | 1.258 | 8.447 | 23.457 | 9.851 | 82.637 |
| `conversion/temperature/ndarray/1000` | 1.253 | 6.068 | 38.030 | 28.034 | 65.908 |
| `arithmetic/add_compatible/ndarray/1000` | 2.313 | 5.779 | 32.481 | 13.717 | 12.654 |
| `arithmetic/multiply/ndarray/1000` | 0.958 | 1.192 | 13.012 | 8.751 | 18.903 |
| `arithmetic/sqrt/ndarray/1000` | 2.078 | 3.268 | 12.994 | 8.082 | 20.066 |
| `numpy/np_add/ndarray/1000` | 1.046 | 5.777 | 35.141 | 8.650 | 8.489 |
| `numpy/np_sqrt/ndarray/1000` | 2.077 | 4.582 | 21.402 | 7.142 | 18.557 |
| `numpy/np_sum/ndarray/1000` | 2.526 | 1.820 | 55.821 | 11.757 | 11.625 |
| `arithmetic/add_compatible/ndarray/1000000` | 2693.769 | 1423.364 | 704.002 | 2724.641 | 677.668 |

The artifact contains the full CSV, per-sample CSV, raw pyperf JSON, figure, and effective configuration.
GitHub-hosted runner timings can vary with machine load; compare runs with matching environments and settings.
