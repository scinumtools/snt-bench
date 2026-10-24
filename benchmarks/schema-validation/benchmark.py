"""Check fixture parity, then time complete command-line validation workflows."""

import argparse
import csv
from datetime import datetime, timezone
import fnmatch
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

_mpl_cache = Path(tempfile.gettempdir()) / "snt-bench-schema-validation-matplotlib"
_mpl_cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_mpl_cache))
os.environ.setdefault("XDG_CACHE_HOME", str(_mpl_cache))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from scinumtools3.dip import DIP


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DEFAULT_CONFIG = HERE / "config.dip"
PARTICIPANTS = ("dipl", "jsonschema", "cue", "pkl")
COLORS = {"dipl": "#0072B2", "jsonschema": "#E69F00", "cue": "#009E73", "pkl": "#D55E00"}


def as_list(value):
    return value if isinstance(value, list) else [value]


def load_config(path):
    parser = DIP()
    parser.add_file(path)
    env = parser.parse()
    prefix = "schema_validation."

    def get(key):
        return env[prefix + key].value

    return get


def project_path(configured):
    path = Path(configured)
    return path if path.is_absolute() else REPO / path


def json_scalar(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def dipl_document(data, root="simulation"):
    lines = [f"{root} : runconfig"]
    for field in ("name", "mode"):
        if field in data:
            lines.append(f"  {field} = {json_scalar(data[field])}")
    if "steps" in data:
        lines.append(f"  steps = {data['steps']}")
    if "grid" in data:
        lines.append("  grid")
        for field in ("nx", "ny"):
            if field in data["grid"]:
                value = json_scalar(data["grid"][field]) if isinstance(data["grid"][field], str) else data["grid"][field]
                lines.append(f"    {field} = {value}")
        if "spacing_m" in data["grid"]:
            lines.append(f"    spacing_m = {data['grid']['spacing_m']!r} m")
    return "\n".join(lines) + "\n"


def pkl_document(data):
    lines = [
        'import "schema.pkl"',
        "",
        "run: schema.Run = new {",
    ]
    for field in ("name", "mode", "steps"):
        if field in data:
            lines.append(f"  {field} = {json_scalar(data[field])}")
    if "grid" in data:
        lines.append("  grid = new schema.Grid {")
        for field in ("nx", "ny", "spacing_m"):
            if field in data["grid"]:
                lines.append(f"    {field} = {json_scalar(data['grid'][field])}")
        lines.append("  }")
    lines.extend(["}", "", "output {", "  value = run", "}"])
    return "\n".join(lines) + "\n"


def prepare_fixtures(cases, paths):
    pkl_schema = paths["generated"] / "schema.pkl"
    shutil.copyfile(paths["pkl_schema"], pkl_schema)
    dipl_schema = paths["generated"] / "schema.dip"
    shutil.copyfile(paths["dipl_schema"], dipl_schema)
    for item in cases:
        stem = item["id"].replace("/", "--")
        item["data_path"] = paths["generated"] / f"{stem}.json"
        item["dipl_path"] = paths["generated"] / f"{stem}.dip"
        item["dipl_project"] = paths["generated"] / f"{stem}.DIPfile"
        item["pkl_path"] = paths["generated"] / f"{stem}.pkl"
        item["data_path"].write_text(json.dumps(item["data"], indent=2) + "\n", encoding="utf-8")
        group_name = "simulation_" + re.sub(r"[^a-zA-Z0-9_]", "_", item["id"])
        item["dipl_path"].write_text(dipl_document(item["data"], group_name), encoding="utf-8")
        project = ("schemas[]\n"
                   '  name = "runconfig"\n'
                   '  file = "schema.dip"\n\n'
                   "code[]\n"
                   f'  file = "{item["dipl_path"].name}"\n')
        item["dipl_project"].write_text(project, encoding="utf-8")
        item["pkl_path"].write_text(pkl_document(item["data"]), encoding="utf-8")


def cli_version(command):
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    return (result.stdout + result.stderr).strip()


def confirm_versions(participants, get):
    installed = {}
    if "dipl" in participants:
        command = str(get("workload.snt_command"))
        if shutil.which(command) is None:
            raise SystemExit(f"SNT CLI is not installed or not on PATH: {command}")
        output = cli_version([command, "--version"])
        match = re.search(r"\d+\.\d+\.\d+", output)
        installed["dipl"] = match.group(0) if match else output
        expected = str(get("packages.scinumtools3.version"))
        if installed["dipl"] != expected:
            raise SystemExit(f"Requires SNT CLI {expected}; found {output}")
    if "jsonschema" in participants:
        installed["jsonschema"] = importlib.metadata.version("jsonschema")
        expected = str(get("packages.jsonschema.version"))
        if installed["jsonschema"] != expected:
            raise SystemExit(f"Requires jsonschema=={expected}; found {installed['jsonschema']}")
    if "cue" in participants:
        command = str(get("workload.cue_command"))
        if shutil.which(command) is None:
            raise SystemExit(f"CUE is not installed or not on PATH: {command} (pin {get('packages.cue.version')})")
        output = cli_version([command, "version"])
        match = re.search(r"v?\d+\.\d+\.\d+", output)
        installed["cue"] = match.group(0).lstrip("v") if match else output
        if installed["cue"] != str(get("packages.cue.version")):
            raise SystemExit(f"Requires CUE {get('packages.cue.version')}; found {output}")
    if "pkl" in participants:
        command = str(get("workload.pkl_command"))
        if shutil.which(command) is None:
            raise SystemExit(f"Pkl is not installed or not on PATH: {command} (pin {get('packages.pkl.version')})")
        output = cli_version([command, "--version"])
        match = re.search(r"\d+\.\d+\.\d+", output)
        installed["pkl"] = match.group(0) if match else output
        if installed["pkl"] != str(get("packages.pkl.version")):
            raise SystemExit(f"Requires Pkl {get('packages.pkl.version')}; found {output}")
    return installed


def command_for(participant, item, paths, get):
    python = sys.executable
    if participant == "dipl":
        return [str(get("workload.snt_command")), "validate", "--project", str(item["dipl_project"])]
    if participant == "jsonschema":
        return [python, str(HERE / "validate_python.py"), "jsonschema",
                "--schema", str(paths["json_schema"]), "--data", str(item["data_path"])]
    if participant == "cue":
        return [str(get("workload.cue_command")), "vet", "-c", "-d", "#Config",
                str(paths["cue_schema"]), str(item["data_path"])]
    if participant == "pkl":
        return [str(get("workload.pkl_command")), "eval", str(item["pkl_path"])]
    raise ValueError(participant)


def batch_command_for(participant, items, paths, get):
    """Validate one class batch in a single native CLI process."""
    if participant == "dipl":
        batch_project = paths["generated"] / f"batch-{items[0]['valid']}.DIPfile"
        lines = ["schemas[]", '  name = "runconfig"', '  file = "schema.dip"']
        for item in items:
            lines.extend(["", "code[]", f'  file = "{item["dipl_path"].name}"'])
        batch_project.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return [str(get("workload.snt_command")), "validate", "--project", str(batch_project)]
    if participant == "jsonschema":
        command = [sys.executable, str(HERE / "validate_python.py"), "jsonschema",
                   "--schema", str(paths["json_schema"])]
        for item in items:
            command.extend(("--data", str(item["data_path"])))
        return command
    if participant == "cue":
        return [str(get("workload.cue_command")), "vet", "-c", "-d", "#Config",
                str(paths["cue_schema"]), *(str(item["data_path"]) for item in items)]
    if participant == "pkl":
        return [str(get("workload.pkl_command")), "eval",
                *(str(item["pkl_path"]) for item in items)]
    raise ValueError(participant)


def run_once(command, expected_valid):
    result = subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    observed_valid = result.returncode == 0
    return observed_valid, result.stderr.decode("utf-8", errors="replace")


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else [])
        if rows:
            writer.writeheader()
            writer.writerows(rows)


def draw_figure(summary, output, dpi):
    classes = ("valid", "invalid")
    fig, ax = plt.subplots(figsize=(8.5, 4.8), layout="constrained")
    participants = list(dict.fromkeys(row["participant"] for row in summary))
    width = 0.19
    positions = list(range(len(participants)))
    for offset, validity in enumerate(classes):
        medians = []
        lower = []
        upper = []
        for participant in participants:
            row = next((row for row in summary
                        if row["participant"] == participant and row["case_class"] == validity), None)
            medians.append(float(row["median_batch_ms"]) if row else float("nan"))
            lower.append(float(row["min_batch_ms"]) if row else float("nan"))
            upper.append(float(row["max_batch_ms"]) if row else float("nan"))
        x = [position + (offset - 0.5) * width for position in positions]
        fixture_count = next((row["fixture_count"] for row in summary
                              if row["case_class"] == validity), 0)
        ax.bar(x, medians, width=width, label=f"{validity.title()} set (n={fixture_count})",
               color="#0072B2" if offset == 0 else "#D55E00",
               yerr=[[median - low for median, low in zip(medians, lower)],
                     [high - median for median, high in zip(medians, upper)]],
               capsize=3, error_kw={"linewidth": 0.8})
    labels = [f"{row['participant']}\n{row['participant_version']}" for row in
              [next(item for item in summary if item["participant"] == participant)
               for participant in participants]]
    ax.set_xticks(positions, labels)
    ax.set_ylabel("Median time for one CLI batch (ms)")
    ax.set_title("Schema/config validation: same-case native CLI batches")
    ax.grid(axis="y", color="#c8cdd3", linewidth=0.6, alpha=0.7)
    ax.legend(frameon=False)
    fig.savefig(output, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    cli.add_argument("--participant", action="append", choices=PARTICIPANTS)
    cli.add_argument("--samples", type=int)
    args = cli.parse_args()
    config_path = args.config.resolve()
    get = load_config(config_path)
    all_cases = json.loads(project_path(get("execution.paths.cases_file")).read_text(encoding="utf-8"))
    patterns = as_list(get("execution.selection.case_ids"))
    cases = [item for item in all_cases if any(fnmatch.fnmatchcase(item["id"], p) for p in patterns)]
    if not cases:
        raise SystemExit("No fixture IDs matched schema_validation.execution.selection.case_ids")
    participants = args.participant or as_list(get("execution.selection.participants"))
    if not participants or len(set(participants)) != len(participants):
        raise SystemExit("Select each supported participant once or more")
    samples = args.samples if args.samples is not None else int(get("timing.quick.samples"))
    warmups = int(get("timing.quick.warmups"))
    if samples < 1 or warmups < 0:
        raise SystemExit("samples must be positive and warmups nonnegative")

    output_dir = project_path(get("execution.paths.output_dir"))
    generated = output_dir / "generated"
    generated.mkdir(parents=True, exist_ok=True)
    paths = {
        "generated": generated,
        "json_schema": project_path(get("execution.paths.json_schema_file")),
        "cue_schema": project_path(get("execution.paths.cue_schema_file")),
        "pkl_schema": project_path(get("execution.paths.pkl_schema_file")),
        "dipl_schema": project_path(get("execution.paths.dipl_schema_file")),
    }
    prepare_fixtures(cases, paths)
    versions = confirm_versions(participants, get)
    commands = {(participant, item["id"]): command_for(participant, item, paths, get)
                for participant in participants for item in cases}

    correctness = []
    for participant in participants:
        for item in cases:
            observed, error = run_once(commands[(participant, item["id"])], item["valid"])
            passed = observed == bool(item["valid"])
            correctness.append({"participant": participant, "case_id": item["id"],
                               "expected_valid": item["valid"], "observed_valid": observed,
                               "status": "PASS" if passed else "FAIL",
                               "diagnostic": "" if passed else error.strip()[:500]})
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    prefix = f"schema_validation_{stamp}"
    write_csv(output_dir / f"{prefix}_correctness.csv", correctness)
    failures = [row for row in correctness if row["status"] != "PASS"]
    if failures:
        print(f"Correctness parity failed for {len(failures)} fixture(s):")
        for row in failures:
            print(f"  {row['participant']} {row['case_id']}: expected valid={row['expected_valid']}, "
                  f"observed valid={row['observed_valid']} {row['diagnostic']}")
        raise SystemExit(1)

    samples_rows = []
    for participant in participants:
        for case_class, expected_valid in (("valid", True), ("invalid", False)):
            batch = [item for item in cases if bool(item["valid"]) == expected_valid]
            if not batch:
                continue
            command = batch_command_for(participant, batch, paths, get)
            for _ in range(warmups):
                observed, error = run_once(command, expected_valid)
                if observed != expected_valid:
                    raise SystemExit(f"Batch warmup failed: {participant} {case_class}: {error}")
            for sample in range(samples):
                start = time.perf_counter_ns()
                observed, error = run_once(command, expected_valid)
                elapsed_ns = time.perf_counter_ns() - start
                if observed != expected_valid:
                    raise SystemExit(f"Batch validation changed during timing: {participant} {case_class}: {error}")
                samples_rows.append({
                    "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "participant": participant,
                    "participant_version": versions[participant],
                    "case_class": case_class,
                    "fixture_count": len(batch),
                    "sample": sample + 1,
                    "batch_elapsed_ns": elapsed_ns,
                    "batch_elapsed_ms": elapsed_ns / 1e6,
                    "ms_per_document": elapsed_ns / 1e6 / len(batch),
                    "platform": platform.platform(),
                    "python_version": platform.python_version(),
                })

    summary = []
    for participant in participants:
        for case_class in ("valid", "invalid"):
            values = [float(row["ms_per_document"]) for row in samples_rows
                      if row["participant"] == participant and row["case_class"] == case_class]
            batch_values = [float(row["batch_elapsed_ms"]) for row in samples_rows
                            if row["participant"] == participant and row["case_class"] == case_class]
            if values and batch_values:
                summary.append({
                    "participant": participant,
                    "participant_version": versions[participant],
                    "case_class": case_class,
                    "fixture_count": next(row["fixture_count"] for row in samples_rows
                                           if row["participant"] == participant and row["case_class"] == case_class),
                    "samples_per_batch": samples,
                    "median_batch_ms": statistics.median(batch_values),
                    "min_batch_ms": min(batch_values),
                    "max_batch_ms": max(batch_values),
                    "median_ms_per_document": statistics.median(values),
                    "min_ms_per_document": min(values),
                    "max_ms_per_document": max(values),
                })
    samples_path = output_dir / f"{prefix}_samples.csv"
    summary_path = output_dir / f"{prefix}_summary.csv"
    figure_path = output_dir / f"{prefix}.png"
    write_csv(samples_path, samples_rows)
    write_csv(summary_path, summary)
    draw_figure(summary, figure_path, 300)
    config_text = config_path.read_text(encoding="utf-8")
    snapshot = {
        "config_path": str(config_path),
        "config_sha256": hashlib.sha256(config_text.encode()).hexdigest(),
        "participants": versions,
        "case_ids": [item["id"] for item in cases],
        "samples": samples,
        "warmups": warmups,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
    }
    (output_dir / f"{prefix}.config.json").write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(f"Correctness: {output_dir / f'{prefix}_correctness.csv'} (all cases passed)")
    print(f"Summary: {summary_path}")
    print(f"Figure:  {figure_path}")
    for row in summary:
        print(f"{row['participant']} {row['participant_version']} {row['case_class']}: "
              f"median {row['median_batch_ms']:.3f} ms for a {row['fixture_count']}-document batch")


if __name__ == "__main__":
    main()
