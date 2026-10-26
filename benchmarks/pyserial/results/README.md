# Reference parsing results

The committed [CSV](reference-quick.csv), [parser-output-only figure](reference-quick.png), [common-mapping figure](reference-common-mapping.png), and [effective configuration](reference-quick.config.json) record a full pinned quick run on 2026-10-26 at 19:03 UTC using CPython 3.13.15 on macOS arm64 and SNT3 0.9.11. The CSV contains both measurement paths for all 16 format-and-size combinations; all passed equality checks. The run used two warmups, five timed samples, and a 10 ms target duration per sample.

Timestamped local runs are ignored by Git. To refresh this reference, run `./setup.sh --benchmark pyserial`, inspect its output and environment metadata, then deliberately replace the four reference data/figure files and update the result discussion in the benchmark README.
