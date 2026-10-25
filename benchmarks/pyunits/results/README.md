# Pyunits result snapshots

`reference-quick.csv`, `reference-quick_samples.csv`, `reference-quick.config.json`, and `reference-quick.png` are a curated full-matrix quick run pinned to SNT3 0.9.10, recorded on 2026-10-25 at 12:05 UTC. The main README gives its environment and a selection of its timings. Quick results are single-process development measurements.

`github-pyperf-40137348007.*` archives the representative CI pyperf run and its figure, summary, raw measurements, and configuration. See the [pyunits README](../README.md#github-actions-pyperf-screen) for its scope and interpretation.

Normal invocations write timestamped files here. Those files are ignored by Git so a partial rerun cannot silently replace the reference. Review the output and explicitly update the `reference-quick` files and provenance note when adopting a new snapshot. Pyperf JSON is retained locally by default; archive it alongside any published pyperf result.
