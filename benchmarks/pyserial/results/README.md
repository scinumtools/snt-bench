# Reference parsing results

The committed [CSV](reference-quick.csv), [figure](reference-quick.png), and [effective configuration](reference-quick.config.json) record a full pinned quick run on 2026-10-25 at 11:44 UTC using CPython 3.13.15 on macOS arm64 and SNT3 0.9.10. All 16 format-and-size results passed exact-value checks. The run used two warmups, five timed samples, and a 10 ms target duration per sample.

Timestamped local runs are ignored by Git. To refresh this reference, run `./setup.sh --benchmark pyserial`, inspect its output and environment metadata, then deliberately replace the three `reference-quick` files and update the result discussion in the benchmark README.
