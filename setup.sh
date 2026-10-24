#!/usr/bin/env bash
set -euo pipefail
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "${PYTHON_LAUNCHER:-python3}" "$repo_dir/benchmarks/pyunits/run.py" "$@"
