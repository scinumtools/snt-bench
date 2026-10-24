# Pyunits result snapshots

`reference-quick.csv`, `reference-quick_samples.csv`, `reference-quick.config.json`, and `reference-quick.png` are a curated full-matrix quick run of the pinned release, recorded on 2026-10-24 at 19:09 UTC. The main README gives its environment and a selection of its timings. Quick results are single-process development measurements.

Normal invocations write timestamped files here. Those files are ignored by Git so a partial rerun cannot silently replace the reference. Review the output and explicitly update the `reference-quick` files and provenance note when adopting a new snapshot. Pyperf JSON is retained locally by default; archive it alongside any published pyperf result.
