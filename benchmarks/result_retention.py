"""Keep only the newest timestamped benchmark result sets in a directory."""

from pathlib import Path
import re


KEEP_RUNS = 10
TIMESTAMP = re.compile(r"20\d{6}T\d{6}Z")


def prune_old_results(results_dir, keep=KEEP_RUNS):
    """Remove complete timestamped result sets older than the newest ``keep``.

    Files without a timestamp (curated reference results, for example) and
    files in subdirectories are left untouched.
    """
    results_dir = Path(results_dir)
    groups = {}
    for path in results_dir.iterdir():
        if not path.is_file():
            continue
        match = TIMESTAMP.search(path.name)
        if match:
            groups.setdefault(match.group(), []).append(path)

    retained = set(sorted(groups, reverse=True)[:keep])
    removed = []
    for stamp, paths in groups.items():
        if stamp not in retained:
            for path in paths:
                path.unlink()
                removed.append(path)
    return removed
