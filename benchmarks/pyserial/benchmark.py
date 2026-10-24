"""Compare Python parsing of equivalent YAML, TOML, JSON, and DIPL data."""

import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import statistics
import tempfile
import time
import tomllib

_mpl_cache = Path(tempfile.gettempdir()) / "snt-bench-pyserial-matplotlib"
_mpl_cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_mpl_cache))
os.environ.setdefault("XDG_CACHE_HOME", str(_mpl_cache))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import yaml

from scinumtools3.dip import DIP
import scinumtools3


HERE = Path(__file__).resolve().parent
REPO_DIR = HERE.parents[1]
DEFAULT_CONFIG = HERE / "config.dip"
FORMATS = ("json", "yaml", "toml", "dipl")
COLORS = {"json": "#666666", "yaml": "#0072B2", "toml": "#E69F00", "dipl": "#009E73"}
LINE_STYLES = {"json": "-", "yaml": "--", "toml": ":", "dipl": "-."}


def as_list(value):
    return value if isinstance(value, list) else [value]


def parameter_name(index, settings):
    return f"{settings['name_prefix']}{index:0{settings['name_min_digits']}d}"


def make_data(count, settings):
    return {
        "experiment": {
            "name": settings["experiment_name"],
            "enabled": settings["experiment_enabled"],
            "iterations": settings["experiment_iterations"],
            "timestep": settings["experiment_timestep"],
            "parameters": {parameter_name(i, settings):
                           (i % settings["value_period"]) / settings["value_divisor"]
                           for i in range(count)},
        }
    }


def toml_scalar(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return repr(value)


def toml_document(data):
    experiment = data["experiment"]
    lines = ["[experiment]"]
    for key in ("name", "enabled", "iterations", "timestep"):
        lines.append(f"{key} = {toml_scalar(experiment[key])}")
    lines.extend(("", "[experiment.parameters]"))
    lines.extend(f"{key} = {toml_scalar(value)}"
                 for key, value in experiment["parameters"].items())
    return "\n".join(lines) + "\n"


def dipl_document(data):
    experiment = data["experiment"]
    lines = [
        "experiment",
        f"  name str = {json.dumps(experiment['name'], ensure_ascii=False)}",
        f"  enabled bool = {'true' if experiment['enabled'] else 'false'}",
        f"  iterations int = {experiment['iterations']}",
        f"  timestep float = {repr(experiment['timestep'])}",
        "  parameters",
    ]
    lines.extend(f"    {key} float = {repr(value)}"
                 for key, value in experiment["parameters"].items())
    return "\n".join(lines)


def encode(fmt, data):
    if fmt == "json":
        return json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if fmt == "yaml":
        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    if fmt == "toml":
        return toml_document(data)
    if fmt == "dipl":
        return dipl_document(data)
    raise ValueError(fmt)


def write_if_changed(path, content):
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def decode(fmt, payload, count, settings):
    if fmt == "json":
        return json.loads(payload)
    if fmt == "yaml":
        return yaml.safe_load(payload)
    if fmt == "toml":
        return tomllib.loads(payload)
    if fmt == "dipl":
        parser = DIP()
        parser.add_string(payload)
        env = parser.parse()
        root = "experiment"
        values = {node.name: node.value for node in env.select("?")}
        experiment = {
            "name": values[f"{root}.name"],
            "enabled": values[f"{root}.enabled"],
            "iterations": values[f"{root}.iterations"],
            "timestep": values[f"{root}.timestep"],
            "parameters": {parameter_name(i, settings):
                           values[f"{root}.parameters.{parameter_name(i, settings)}"]
                           for i in range(count)},
        }
        return {root: experiment}
    raise ValueError(fmt)


def measure(function, samples, warmups, target_ms, max_loops):
    for _ in range(warmups):
        function()
    loops = 1
    while True:
        start = time.perf_counter()
        for _ in range(loops):
            function()
        elapsed = time.perf_counter() - start
        if elapsed * 1000 >= target_ms or loops >= max_loops:
            break
        loops = min(max_loops, max(loops + 1, int(loops * target_ms / max(elapsed * 1000, 0.01))))
    per_call = []
    for _ in range(samples):
        start = time.perf_counter()
        for _ in range(loops):
            function()
        per_call.append((time.perf_counter() - start) / loops)
    return statistics.median(per_call), statistics.quantiles(per_call, n=4)[2] - statistics.quantiles(per_call, n=4)[0], loops


def main():
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    pre_args, _ = pre_parser.parse_known_args()
    config_path = pre_args.config.resolve()
    dip = DIP()
    dip.add_file(config_path)
    config = dip.parse()

    def get(path):
        return config[f"pyserial.{path}"].value

    def output_path(path):
        value = Path(get(path))
        return value if value.is_absolute() else REPO_DIR / value

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=config_path)
    parser.add_argument("--output", type=Path, default=output_path("execution.outputs.results_dir") / "latest.csv")
    parser.add_argument("--figure", type=Path, default=output_path("execution.outputs.results_dir") / "latest.png")
    parser.add_argument("--documents-dir", type=Path, default=output_path("execution.outputs.documents_dir"))
    parser.add_argument("--size", action="append", type=int, help="Parameter count; repeat to select sizes")
    parser.add_argument("--format", action="append", choices=FORMATS, help="Parser; repeat to select formats")
    parser.add_argument("--samples", type=int, default=get("timing.quick.samples"))
    parser.add_argument("--warmups", type=int, default=get("timing.quick.warmups"))
    parser.add_argument("--target-ms", type=float, default=get("timing.quick.target_ms"))
    parser.add_argument("--max-loops", type=int, default=get("timing.quick.max_loops"))
    args = parser.parse_args()
    sizes = args.size if args.size is not None else as_list(get("execution.selection.parameter_counts"))
    formats = args.format if args.format is not None else as_list(get("execution.selection.formats"))
    settings = {
        "experiment_name": get("workload.experiment.name"),
        "experiment_enabled": get("workload.experiment.enabled"),
        "experiment_iterations": get("workload.experiment.iterations"),
        "experiment_timestep": get("workload.experiment.timestep"),
        "name_prefix": get("workload.parameters.name_prefix"),
        "name_min_digits": get("workload.parameters.name_min_digits"),
        "value_period": get("workload.parameters.value_period"),
        "value_divisor": get("workload.parameters.value_divisor"),
    }
    if args.samples < 2 or args.warmups < 0 or args.target_ms <= 0 or args.max_loops < 1 or any(n < 1 for n in sizes):
        parser.error("samples >= 2, warmups >= 0, target-ms > 0, max-loops >= 1, and sizes >= 1 are required")
    if not sizes or len(set(sizes)) != len(sizes):
        parser.error("sizes must be unique")
    if not formats or len(set(formats)) != len(formats) or set(formats) - set(FORMATS):
        parser.error("formats must be unique supported parser names")
    if (not re.fullmatch(r"[a-z_][a-z0-9_]*", settings["name_prefix"])
            or settings["name_min_digits"] < 1 or settings["value_period"] < 1
            or settings["value_divisor"] <= 0):
        parser.error("invalid workload.parameters settings")

    rows = []
    exported_documents = False
    for count in sizes:
        data = make_data(count, settings)
        expected = data
        for fmt in formats:
            payload = encode(fmt, data)
            actual = decode(fmt, payload, count, settings)
            if actual != expected:
                raise AssertionError(f"{fmt} did not reproduce the canonical structure at size {count}")
            if get("execution.outputs.export_smallest") and not exported_documents:
                extensions = {"json": "json", "yaml": "yaml", "toml": "toml", "dipl": "dipl"}
                write_if_changed(
                    args.documents_dir / f"parameters_{count}.{extensions[fmt]}", payload
                )
            median, iqr, loops = measure(
                lambda: decode(fmt, payload, count, settings), args.samples, args.warmups,
                args.target_ms, args.max_loops
            )
            rows.append({
                "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "format": fmt,
                "parameters": count,
                "payload_bytes": len(payload.encode("utf-8")),
                "median_seconds": median,
                "iqr_seconds": iqr,
                "loops_per_sample": loops,
                "samples": args.samples,
                "warmups": args.warmups,
                "target_ms": args.target_ms,
                "python_version": platform.python_version(),
                "implementation": platform.python_implementation(),
                "platform": platform.platform(),
                "json_parser": f"stdlib/{platform.python_version()}",
                "yaml_parser": f"PyYAML/{yaml.__version__}",
                "toml_parser": f"tomllib/{platform.python_version()}",
                "scinumtools3_version": scinumtools3.__version__,
                "status": "PASS",
            })
        exported_documents = True

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    args.figure.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), layout="constrained")
    for fmt in formats:
        points = [row for row in rows if row["format"] == fmt]
        xs = [row["parameters"] for row in points]
        times_ms = [row["median_seconds"] * 1e3 for row in points]
        style = {"marker": "o", "markersize": 5, "linewidth": 2,
                 "linestyle": LINE_STYLES[fmt], "color": COLORS[fmt], "label": fmt.upper()}
        axes[0].plot(xs, times_ms, **style)
        axes[1].plot([row["payload_bytes"] for row in points], times_ms, **style)
    for ax in axes:
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.grid(which="both", color="#c8cdd3", linewidth=0.6, alpha=0.7)
    axes[0].set_xlabel("Number of scalar parameters")
    axes[0].set_xticks(sizes, labels=[str(size) for size in sizes])
    axes[0].set_ylabel("Median parse time (ms)")
    axes[0].set_title("Parameters vs. parse time")
    axes[1].set_xlabel("Encoded document size (bytes)")
    axes[1].set_ylabel("Median parse time (ms)")
    axes[1].set_title("Payload vs. parse time")
    axes[1].legend(title="Format / Python parser", frameon=False)
    fig.suptitle("Python parsing of equivalent configuration data")
    fig.savefig(args.figure, dpi=get("execution.outputs.figure_dpi"), bbox_inches="tight")
    print(f"Results: {args.output}")
    print(f"Figure:  {args.figure}")
    print(pd.DataFrame(rows)[["format", "parameters", "payload_bytes", "median_seconds", "status"]]
          .to_string(index=False, formatters={"median_seconds": lambda value: f"{value * 1e3:.3f} ms"}))


if __name__ == "__main__":
    main()
