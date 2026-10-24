# Uncertainty propagation result files

The `reference-quick` files are the curated run shown in the main README. New
timestamped run sets are created by `./setup.sh --benchmark
uncertainty-propagation --quick`; only the newest ten timestamped run groups are
retained. Each run includes per-case CSV data, a figure, and a JSON manifest
with the effective configuration source and hash, package pins, and portable
system metadata.
