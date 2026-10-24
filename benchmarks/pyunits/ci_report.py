"""Expose DIPL settings to Actions and summarize a pyperf run."""

import argparse
import csv
import json
import os
from pathlib import Path
import re

from benchmark_config import DEFAULT_CONFIG, literal_string


REPO_DIR = Path(__file__).resolve().parents[2]


def github_output(name, value):
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with Path(output).open("a") as stream:
            stream.write(f"{name}={value}\n")


def python_version(config_path):
    # setup-python runs before scinumtools3 is installed on the hosted runner.
    executable = literal_string(config_path.read_text(), "pyunits.execution.paths.python_base")
    match = re.fullmatch(r"python(\d+\.\d+)", executable)
    if not match:
        raise SystemExit("The pinned workflow requires python_base in the form python3.13")
    github_output("python-version", match.group(1))
    print(f"Python from {config_path}: {match.group(1)}")


def report(config_path, snapshot_path):
    from scinumtools3.dip import DIP

    dip = DIP()
    dip.add_file(config_path)
    values = dip.parse()
    results_dir = Path(values["pyunits.execution.paths.output_dir"].value)
    if not results_dir.is_absolute():
        results_dir = REPO_DIR / results_dir
    if snapshot_path is None:
        candidates = list(results_dir.glob("pyunits_pinned_pyperf_*.config.json"))
        if len(candidates) != 1:
            raise SystemExit(f"Expected one new pyperf snapshot in {results_dir}, found {len(candidates)}")
        snapshot_path = candidates[0]
    snapshot_path = snapshot_path.resolve()
    base = snapshot_path.with_name(snapshot_path.name.removesuffix(".config.json"))
    files = [base.with_suffix(".csv"), base.with_name(base.name + "_samples.csv"),
             base.with_suffix(".pyperf.json"), base.with_suffix(".png"), snapshot_path]
    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        raise SystemExit("Missing pyperf result files: " + ", ".join(missing))

    snapshot = json.loads(snapshot_path.read_text())
    settings = snapshot["settings"]
    if (settings["benchmark"], settings["source"], settings["mode"]) != ("pyunits", "pinned", "pyperf"):
        raise SystemExit("The result snapshot is not a pinned pyperf matrix run")
    with files[0].open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise SystemExit("The pyperf summary CSV is empty")

    by_case = {}
    for row in rows:
        by_case.setdefault(row["case_id"], {})[row["library"]] = row
    libraries = settings["libraries"]
    passed = sum(row["status"] == "PASS" for row in rows)
    unsupported = sum(row["status"] == "UNSUPPORTED" for row in rows)
    if passed + unsupported != len(rows):
        raise SystemExit("The pyperf summary contains unsuccessful rows")

    first = rows[0]
    package_versions = ", ".join(
        f"{library} {snapshot['projects'][library]['version']}" for library in (*libraries, "numpy")
    )
    process_count = settings["processes"]
    value_count = settings["values"]
    case_count = len(by_case)
    lines = [
        "# Python units: pyperf comparison",
        "",
        f"Run: {first['run_utc']} on {first['platform']} ({first['architecture']}); Python {first['python_version']}.",
        f"Checks: **{passed}/{len(rows)} PASS** across {case_count} {'case' if case_count == 1 else 'cases'}"
        + (f"; {unsupported} unsupported" if unsupported else "") + ".",
        f"Measurement: {process_count} {'process' if process_count == 1 else 'processes'}, "
        f"{value_count} {'value' if value_count == 1 else 'values'} and "
        f"{settings['warmups']} warmups per process; minimum {settings['min_time']} s per value.",
        f"Sizes: {', '.join(map(str, settings['sizes']))}. Packages: {package_versions}.",
        f"Configuration SHA-256: `{snapshot['config_sha256']}`.",
        "",
        "Median microseconds per operation; lower is faster. NumPy is an unranked numeric baseline.",
        "",
        "| Case | NumPy | " + " | ".join(libraries) + " |",
        "| --- | ---: | " + " | ".join("---:" for _ in libraries) + " |",
    ]
    for case_id, library_rows in by_case.items():
        baseline = next(iter(library_rows.values()))["numpy_median_seconds"]
        cells = []
        for library in libraries:
            row = library_rows.get(library)
            cells.append(f"{float(row['median_seconds']) * 1e6:.3f}" if row and row["status"] == "PASS" else "n/a")
        lines.append(f"| `{case_id}` | {float(baseline) * 1e6:.3f} | " + " | ".join(cells) + " |")
    lines.extend(["", "The artifact contains the full CSV, per-sample CSV, raw pyperf JSON, figure, and effective configuration.",
                  "GitHub-hosted runner timings can vary with machine load; compare runs with matching environments and settings.", ""])
    summary = "\n".join(lines)
    summary_path = base.with_suffix(".summary.md")
    summary_path.write_text(summary)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a") as stream:
            stream.write(summary)
    github_output("result_base", base)
    print(f"Wrote {summary_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("python-version", "report"))
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--snapshot", type=Path, help="A specific snapshot, useful for inspecting an earlier run")
    args = parser.parse_args()
    config_path = args.config.resolve()
    if args.command == "python-version":
        python_version(config_path)
    else:
        report(config_path, args.snapshot)


if __name__ == "__main__":
    main()
