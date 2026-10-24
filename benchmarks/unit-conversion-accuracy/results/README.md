# Unit conversion accuracy result files

The `reference-quick` files are the curated run shown in the main README. New
timestamped run sets are created by `./setup.sh --benchmark
unit-conversion-accuracy --quick`; only the newest ten timestamped run groups are
retained. Each run includes long-form per-input CSV data, a figure, and a JSON
manifest with the effective configuration source and hash, package pins, and
portable system metadata.
