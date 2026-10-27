# Pyunits result snapshots

`reference-quick.csv`, `reference-quick_samples.csv`, `reference-quick.config.json`, and `reference-quick.png` are a curated full-matrix quick run pinned to SNT3 0.9.12, recorded on 2026-10-27 at 00:25 UTC. The main README gives its environment and a selection of its timings. Quick results are single-process development measurements.

`reference-pyperf-ci.*` and `reference-pyperf-ci_samples.csv` record the 0.9.12 pinned run of the representative CI profile on macOS arm64. `github-pyperf-40137348007.*` archives the earlier GitHub Actions run. See the [pyunits README](../README.md#pyperf-screening-run) for their scope and interpretation.

Normal invocations write timestamped files here. Those files are ignored by Git so a partial rerun cannot silently replace the reference. Review the output and explicitly update the `reference-quick` files and provenance note when adopting a new snapshot. Pyperf JSON is retained locally by default; archive it alongside any published pyperf result.
