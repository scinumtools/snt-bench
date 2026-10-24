"""Compare the DIPL and JSON Schema Python APIs without child-process startup."""

import argparse
from datetime import datetime, timezone
import fnmatch
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import statistics
import tempfile
import time

_mpl_cache = Path(tempfile.gettempdir()) / "snt-bench-schema-validation-matplotlib"
_mpl_cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_mpl_cache))
os.environ.setdefault("XDG_CACHE_HOME", str(_mpl_cache))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from benchmark import (
    DEFAULT_CONFIG,
    as_list,
    load_config,
    prepare_fixtures,
    project_path,
    write_csv,
)
from scinumtools3.dip import DIP


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "benchmarks"))
from result_retention import prune_old_results
from result_metadata import path_label, platform_label, sanitize_result_metadata

PARTICIPANTS = ("dipl", "jsonschema")
COLORS = {"dipl": "#0072B2", "jsonschema": "#E69F00"}


def validate_batch(participant, items, paths):
    """Run one parser/schema setup and validate every document in the batch."""
    if participant == "dipl":
        parser = DIP()
        parser.add_schema_file("runconfig", str(paths["dipl_schema"]))
        for item in items:
            parser.add_string(item["dipl_path"].read_text(encoding="utf-8"))
        try:
            parser.parse()
            return True, ""
        except Exception as exc:
            return False, str(exc)

    if participant == "jsonschema":
        from jsonschema import Draft202012Validator

        schema = json.loads(paths["json_schema"].read_text(encoding="utf-8"))
        validator = Draft202012Validator(schema)
        valid = []
        for item in items:
            data = json.loads(item["data_path"].read_text(encoding="utf-8"))
            valid.append(validator.is_valid(data))
        return all(valid), ""

    raise ValueError(participant)


def draw_figure(summary, output):
    classes = ("valid", "invalid")
    participants = list(dict.fromkeys(row["participant"] for row in summary))
    positions = list(range(len(participants)))
    width = 0.28
    fig, ax = plt.subplots(figsize=(7.6, 4.5), layout="constrained")
    for offset, case_class in enumerate(classes):
        rows = [next((row for row in summary
                      if row["participant"] == name and row["case_class"] == case_class), None)
                for name in participants]
        medians = [float(row["median_ms"]) if row else float("nan") for row in rows]
        lows = [float(row["min_ms"]) if row else float("nan") for row in rows]
        highs = [float(row["max_ms"]) if row else float("nan") for row in rows]
        x = [position + (offset - 0.5) * width for position in positions]
        count = next((row["fixture_count"] for row in rows if row), 0)
        ax.bar(
            x,
            medians,
            width=width,
            label=f"{case_class.title()} batch (n={count})",
            color="#0072B2" if offset == 0 else "#D55E00",
            yerr=[[median - low for median, low in zip(medians, lows)],
                  [high - median for median, high in zip(medians, highs)]],
            capsize=3,
            error_kw={"linewidth": 0.8},
        )
    labels = [f"{row['participant']}\n{row['participant_version']}" for row in
              [next(row for row in summary if row["participant"] == participant)
               for participant in participants]]
    ax.set_xticks(positions, labels)
    ax.set_ylabel("Median in-process API time per batch (ms)")
    ax.set_title("Python validation APIs: same-case batches")
    ax.grid(axis="y", color="#c8cdd3", linewidth=0.6, alpha=0.7)
    ax.legend(frameon=False)
    fig.savefig(output, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    cli.add_argument("--participant", action="append", choices=PARTICIPANTS)
    cli.add_argument("--samples", type=int)
    args = cli.parse_args()

    config_path = args.config.resolve()
    get = load_config(config_path)
    case_file = project_path(get("execution.paths.cases_file"))
    all_cases = json.loads(case_file.read_text(encoding="utf-8"))
    patterns = as_list(get("execution.selection.case_ids"))
    cases = [item for item in all_cases
             if any(fnmatch.fnmatchcase(item["id"], pattern) for pattern in patterns)]
    if not cases:
        raise SystemExit("No fixture IDs matched schema_validation.execution.selection.case_ids")

    participants = args.participant or as_list(get("execution.selection.inprocess_participants"))
    if len(set(participants)) != len(participants):
        raise SystemExit("Select each in-process participant once")
    samples = args.samples if args.samples is not None else int(get("timing.inprocess.samples"))
    warmups = int(get("timing.inprocess.warmups"))
    if samples < 1 or warmups < 0:
        raise SystemExit("samples must be positive and warmups nonnegative")

    output_dir = project_path(get("execution.paths.output_dir"))
    generated = output_dir / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    paths = {
        "generated": generated,
        "json_schema": project_path(get("execution.paths.json_schema_file")),
        "pkl_schema": project_path(get("execution.paths.pkl_schema_file")),
        "dipl_schema": project_path(get("execution.paths.dipl_schema_file")),
    }
    prepare_fixtures(cases, paths)

    versions = {
        "dipl": importlib.metadata.version("scinumtools3"),
        "jsonschema": importlib.metadata.version("jsonschema"),
    }
    if versions["dipl"] != str(get("packages.scinumtools3.version")):
        raise SystemExit(f"Requires scinumtools3=={get('packages.scinumtools3.version')}; found {versions['dipl']}")
    if versions["jsonschema"] != str(get("packages.jsonschema.version")):
        raise SystemExit(f"Requires jsonschema=={get('packages.jsonschema.version')}; found {versions['jsonschema']}")

    # Check the expected acceptance result for every selected fixture individually.
    correctness = []
    for participant in participants:
        for item in cases:
            observed, error = validate_batch(participant, [item], paths)
            passed = observed == bool(item["valid"])
            correctness.append({
                "participant": participant,
                "case_id": item["id"],
                "expected_valid": item["valid"],
                "observed_valid": observed,
                "status": "PASS" if passed else "FAIL",
                "diagnostic": "" if passed else error.strip()[:500],
            })
    failures = [row for row in correctness if row["status"] != "PASS"]
    if failures:
        raise SystemExit("In-process correctness parity failed: " + json.dumps(failures, indent=2))

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    prefix = f"schema_validation_inprocess_{stamp}"
    write_csv(output_dir / f"{prefix}_correctness.csv", correctness)
    samples_rows = []
    for participant in participants:
        for case_class, expected_valid in (("valid", True), ("invalid", False)):
            batch = [item for item in cases if bool(item["valid"]) == expected_valid]
            if not batch:
                continue
            for _ in range(warmups):
                observed, error = validate_batch(participant, batch, paths)
                if observed != expected_valid:
                    raise SystemExit(f"In-process warmup failed: {participant} {case_class}: {error}")
            for sample in range(samples):
                start = time.perf_counter_ns()
                observed, error = validate_batch(participant, batch, paths)
                elapsed_ns = time.perf_counter_ns() - start
                if observed != expected_valid:
                    raise SystemExit(f"In-process result changed: {participant} {case_class}: {error}")
                samples_rows.append({
                    "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "participant": participant,
                    "participant_version": versions[participant],
                    "case_class": case_class,
                    "fixture_count": len(batch),
                    "sample": sample + 1,
                    "elapsed_ns": elapsed_ns,
                    "elapsed_ms": elapsed_ns / 1e6,
                    "platform": platform_label(),
                    "python_version": platform.python_version(),
                })

    summary = []
    for participant in participants:
        for case_class in ("valid", "invalid"):
            selected = [row for row in samples_rows
                        if row["participant"] == participant and row["case_class"] == case_class]
            if selected:
                values = [float(row["elapsed_ms"]) for row in selected]
                summary.append({
                    "participant": participant,
                    "participant_version": versions[participant],
                    "case_class": case_class,
                    "fixture_count": selected[0]["fixture_count"],
                    "samples_per_batch": samples,
                    "median_ms": statistics.median(values),
                    "min_ms": min(values),
                    "max_ms": max(values),
                })

    summary_path = output_dir / f"{prefix}_summary.csv"
    samples_path = output_dir / f"{prefix}_samples.csv"
    figure_path = output_dir / f"{prefix}.png"
    write_csv(samples_path, samples_rows)
    write_csv(summary_path, summary)
    draw_figure(summary, figure_path)
    config_text = config_path.read_text(encoding="utf-8")
    snapshot = {
        "config_path": path_label(config_path, REPO),
        "config_sha256": hashlib.sha256(config_text.encode()).hexdigest(),
        "method": "in-process Python APIs; no subprocess launched by the timed operation",
        "participants": versions,
        "case_ids": [item["id"] for item in cases],
        "samples": samples,
        "warmups": warmups,
        "python_version": platform.python_version(),
        "platform": platform_label(),
    }
    config_output = output_dir / f"{prefix}.config.json"
    config_output.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(f"Correctness: {output_dir / f'{prefix}_correctness.csv'} (all cases passed)")
    print(f"Summary: {summary_path}")
    print(f"Figure:  {figure_path}")
    print(f"Samples: {samples_path}")
    print(f"Config:  {config_output}")
    for row in summary:
        print(f"{row['participant']} {row['participant_version']} {row['case_class']}: "
              f"median {row['median_ms']:.3f} ms for a {row['fixture_count']}-document batch")
    sanitize_result_metadata(output_dir, REPO)
    removed = prune_old_results(output_dir)
    if removed:
        print(f"Pruned {len(removed)} files from result sets older than the newest 10.")


if __name__ == "__main__":
    main()
