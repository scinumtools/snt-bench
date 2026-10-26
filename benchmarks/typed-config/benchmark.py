"""Benchmark typed scientific-configuration loading workflows."""

import argparse
import csv
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import statistics
import sys
import tempfile
import time
import tomllib
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from result_metadata import path_label, platform_label

_cache = Path(tempfile.gettempdir()) / "snt-bench-typed-config-matplotlib"
_cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_cache))
os.environ.setdefault("XDG_CACHE_HOME", str(_cache))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator
import yaml
from pint import UnitRegistry

from scinumtools3.dip import DIP
import scinumtools3


HERE = Path(__file__).resolve().parent
REPO_DIR = HERE.parents[1]
DEFAULT_CONFIG = HERE / "config.dip"
FORMATS = ("json", "yaml", "toml", "dipl")
COLORS = {"json": "#666666", "yaml": "#0072B2", "toml": "#E69F00", "dipl": "#009E73"}
UNITS = UnitRegistry()
MODEL_SETTINGS = {}


class Grid(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nx: int
    ny: int
    spacing_m: float

    @field_validator("nx", "ny")
    @classmethod
    def check_grid_count(cls, value):
        if value <= MODEL_SETTINGS["minimum_grid_count"]:
            raise ValueError("grid dimensions must exceed the configured minimum")
        return value

    @field_validator("spacing_m", mode="before")
    @classmethod
    def parse_length(cls, value):
        if isinstance(value, str):
            value = UNITS.Quantity(value).to("m").magnitude
        if value <= MODEL_SETTINGS["minimum_grid_spacing"]:
            raise ValueError("grid spacing must exceed the configured minimum")
        return value

    @computed_field
    @property
    def cells(self) -> int:
        return self.nx * self.ny


class ScientificConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    label: str = Field(default_factory=lambda: MODEL_SETTINGS["default_label"])
    mode: str
    steps: int
    timestep: float
    grid: Grid
    parameters: dict[str, float]

    @field_validator("name")
    @classmethod
    def check_name(cls, value):
        if not re.fullmatch(MODEL_SETTINGS["name_pattern"], value):
            raise ValueError("name does not match the configured pattern")
        return value

    @field_validator("mode")
    @classmethod
    def check_mode(cls, value):
        if value not in MODEL_SETTINGS["allowed_modes"]:
            raise ValueError("mode is outside the configured options")
        return value

    @field_validator("steps")
    @classmethod
    def check_steps(cls, value):
        if not MODEL_SETTINGS["minimum_steps"] <= value <= MODEL_SETTINGS["maximum_steps"]:
            raise ValueError("steps are outside the configured bounds")
        return value

    @field_validator("timestep", mode="before")
    @classmethod
    def parse_time(cls, value):
        if isinstance(value, str):
            value = UNITS.Quantity(value).to("s").magnitude
        if value <= MODEL_SETTINGS["minimum_timestep"]:
            raise ValueError("timestep must exceed the configured minimum")
        return value

    @computed_field
    @property
    def duration_s(self) -> float:
        return self.steps * self.timestep

    @computed_field
    @property
    def domain_area_m2(self) -> float:
        return self.grid.nx * self.grid.ny * self.grid.spacing_m * self.grid.spacing_m


def read_config(path):
    dip = DIP()
    dip.add_file(path)
    root = dip.parse()

    def get(path):
        return root[f"typed_config.{path}"].value

    return get


def input_data(get, count):
    w = lambda key: get(f"workload.model.{key}")
    prefix, digits = w("parameter_prefix"), w("parameter_digits")
    return {
        "name": w("name"),
        "mode": w("mode"),
        "steps": w("steps"),
        "timestep": f"{w('timestep')} s",
        "grid": {"nx": w("grid_nx"), "ny": w("grid_ny"),
                 "spacing_m": f"{w('grid_spacing_m')} m"},
        "parameters": {
            f"{prefix}{i:0{digits}d}": (i % w("value_period")) / w("value_divisor")
            for i in range(count)
        },
    }


def toml_scalar(value):
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return repr(value)


def encode(fmt, data):
    if fmt == "json":
        return json.dumps(data, ensure_ascii=False)
    if fmt == "yaml":
        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    if fmt == "toml":
        lines = ["name = " + toml_scalar(data["name"]),
                 "mode = " + toml_scalar(data["mode"]),
                 "steps = " + str(data["steps"]),
                 "timestep = " + repr(data["timestep"]), "",
                 "[grid]"]
        lines.extend(f"{key} = {toml_scalar(value)}" for key, value in data["grid"].items())
        lines.extend(("", "[parameters]"))
        lines.extend(f"{key} = {repr(value)}" for key, value in data["parameters"].items())
        return "\n".join(lines) + "\n"
    raise ValueError(fmt)


def make_dipl(get, data):
    w = lambda key: get(f"workload.model.{key}")
    lines = [
        "$schema grid_schema",
        "  nx int",
        f"    !condition ({{.}} > {w('minimum_grid_count')})",
        "  ny int",
        f"    !condition ({{.}} > {w('minimum_grid_count')})",
        "  spacing_m float m",
        f"    !condition ({{.}} > {w('minimum_grid_spacing')} m)",
        "  cells int",
        "$schema parameter_schema",
        "  value float",
        "$schema config_schema",
        "  name str",
        f'    !format {json.dumps(w("name_pattern"))}',
        f'  label str = {json.dumps(w("default_label"))}',
        "  mode str",
        f'    !options {json.dumps(w("allowed_modes"))}',
        "  steps int",
        f"    !condition ({{.}} >= {w('minimum_steps')} && {{.}} <= {w('maximum_steps')})",
        "  timestep float s",
        f"    !condition ({{.}} > {w('minimum_timestep')} s)",
        "  duration_s float s",
        "  grid : grid_schema",
        "  domain_area_m2 float m2",
        "  parameters map : parameter_schema",
        "config : config_schema",
        f"  name = {json.dumps(data['name'])}",
        f"  mode = {json.dumps(data['mode'])}",
        f"  steps = {data['steps']}",
        f"  timestep = {data['timestep']}",
        f"  duration_s = ({{?config.steps}} * {{?config.timestep}}) s",
        "  grid",
        f"    nx = {data['grid']['nx']}",
        f"    ny = {data['grid']['ny']}",
        f"    spacing_m = {data['grid']['spacing_m']}",
        "    cells = ({?config.grid.nx} * {?config.grid.ny})",
        "  domain_area_m2 = ({?config.grid.nx} * {?config.grid.ny} * {?config.grid.spacing_m} * {?config.grid.spacing_m}) m2",
    ]
    for key, value in data["parameters"].items():
        lines.extend((f"  parameters[{key}]", f"    value = {value!r}"))
    return "\n".join(lines)


def execute(fmt, payload):
    if fmt == "json":
        return ScientificConfig.model_validate_json(payload).model_dump()
    if fmt == "yaml":
        return ScientificConfig.model_validate(yaml.safe_load(payload)).model_dump()
    if fmt == "toml":
        return ScientificConfig.model_validate(tomllib.loads(payload)).model_dump()
    if fmt == "dipl":
        parser = DIP()
        parser.add_string(payload)
        parsed = parser.parse()
        return {node.name: node.value for node in parsed.select("?")}
    raise ValueError(fmt)


def assert_rejects_invalid_cases(get, data, formats):
    cases = []
    invalid = deepcopy(data)
    invalid["name"] = "Invalid name"
    cases.append(("invalid/name-pattern", invalid))
    invalid = deepcopy(data)
    invalid["mode"] = "adaptive"
    cases.append(("invalid/mode-option", invalid))
    invalid = deepcopy(data)
    invalid["steps"] = get("workload.model.maximum_steps") + 1
    cases.append(("invalid/steps-maximum", invalid))
    invalid = deepcopy(data)
    invalid["grid"]["nx"] = 0
    cases.append(("invalid/grid-positive", invalid))
    invalid = deepcopy(data)
    invalid["grid"]["spacing_m"] = "1 kg"
    cases.append(("invalid/grid-dimension", invalid))
    for fmt in formats:
        for case_id, invalid_data in cases:
            payload = make_dipl(get, invalid_data) if fmt == "dipl" else encode(fmt, invalid_data)
            try:
                execute(fmt, payload)
            except Exception:
                continue
            raise AssertionError(f"{fmt} accepted {case_id}")
    return len(cases)


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
    timings = []
    for _ in range(samples):
        start = time.perf_counter()
        for _ in range(loops):
            function()
        timings.append((time.perf_counter() - start) / loops)
    return statistics.median(timings), statistics.quantiles(timings, n=4)[2] - statistics.quantiles(timings, n=4)[0], loops


def plot(rows, output, dpi):
    fig, ax = plt.subplots(figsize=(7.2, 4.5), layout="constrained")
    for fmt in FORMATS:
        points = sorted((row for row in rows if row["format"] == fmt),
                        key=lambda row: int(row["parameters"]))
        if points:
            ax.plot([int(row["parameters"]) for row in points],
                    [float(row["median_seconds"]) * 1e3 for row in points],
                    marker="o", linewidth=1.8, color=COLORS[fmt],
                    label=points[0]["implementation"])
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Named floating-point parameters")
    ax.set_ylabel("Median end-to-end load time (ms)")
    ax.set_title("Typed scientific configuration loading")
    ax.grid(which="both", color="#c8cdd3", linewidth=0.6, alpha=0.7)
    ax.legend(title="Implementation", frameon=False, fontsize=8)
    fig.savefig(output, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--figure", type=Path)
    parser.add_argument("--size", action="append", type=int)
    parser.add_argument("--format", action="append", choices=FORMATS)
    parser.add_argument("--samples", type=int)
    args = parser.parse_args()
    get = read_config(args.config.resolve())
    snt_source = os.environ.get("SNT_BENCH_SOURCE", "pinned")
    snt_local_revision = os.environ.get("SNT_BENCH_LOCAL_REVISION")
    snt_local_diff = os.environ.get("SNT_BENCH_LOCAL_DIFF_SHA256")
    snt_local_status = json.loads(os.environ.get("SNT_BENCH_LOCAL_STATUS", "[]"))
    MODEL_SETTINGS.update({
        key: get(f"workload.model.{key}")
        for key in ("default_label", "name_pattern", "allowed_modes", "minimum_steps",
                    "maximum_steps", "minimum_grid_count", "minimum_timestep",
                    "minimum_grid_spacing")
    })
    sizes = args.size or get("execution.selection.parameter_counts")
    formats = args.format or get("execution.selection.formats")
    samples = args.samples if args.samples is not None else get("timing.quick.samples")
    warmups = get("timing.quick.warmups")
    target_ms, max_loops = get("timing.quick.target_ms"), get("timing.quick.max_loops")
    if not sizes or any(size < 1 for size in sizes) or samples < 2:
        parser.error("sizes must be positive and samples must be at least 2")
    if (not formats or set(formats) - set(FORMATS)
            or len(set(sizes)) != len(sizes) or len(set(formats)) != len(formats)):
        parser.error("formats must be nonempty, unique, and supported; sizes must be unique")
    w = lambda key: get(f"workload.model.{key}")
    if (not re.fullmatch(r"[a-z_][a-z0-9_]*", w("parameter_prefix"))
            or w("parameter_digits") < 1 or w("value_period") < 1
            or w("value_divisor") <= 0):
        parser.error("invalid generated parameter naming or value settings")

    rows = []
    for count in sizes:
        data = input_data(get, count)
        canonical = ScientificConfig.model_validate(data).model_dump()
        invalid_cases_checked = assert_rejects_invalid_cases(get, data, formats)
        for fmt in formats:
            payload = make_dipl(get, data) if fmt == "dipl" else encode(fmt, data)
            result = execute(fmt, payload)
            if fmt == "dipl":
                leaves = result
                parameter_values = {
                    key.removeprefix("config.parameters[").split("]", 1)[0]: value
                    for key, value in leaves.items()
                    if key.startswith("config.parameters[")
                }
                result = {
                    "name": leaves["config.name"], "label": leaves["config.label"],
                    "mode": leaves["config.mode"], "steps": leaves["config.steps"],
                    "timestep": leaves["config.timestep"],
                    "grid": {"nx": leaves["config.grid.nx"], "ny": leaves["config.grid.ny"],
                             "spacing_m": leaves["config.grid.spacing_m"],
                             "cells": leaves["config.grid.cells"]},
                    "parameters": parameter_values,
                    "duration_s": leaves["config.duration_s"],
                    "domain_area_m2": leaves["config.domain_area_m2"],
                }
            if result != canonical:
                raise AssertionError(f"{fmt} output differs from the canonical model at {count} parameters")
            median, iqr, loops = measure(
                lambda: execute(fmt, payload), samples, warmups, target_ms, max_loops
            )
            labels = {
                "json": f"JSON / Pydantic {__import__('pydantic').__version__} / Pint {__import__('pint').__version__}",
                "yaml": f"PyYAML {yaml.__version__} / Pydantic {__import__('pydantic').__version__} / Pint {__import__('pint').__version__}",
                "toml": f"tomllib / Pydantic {__import__('pydantic').__version__} / Pint {__import__('pint').__version__}",
                "dipl": (f"DIPL / SNT3 {scinumtools3.__version__}"
                         + (" (local checkout)" if snt_source == "local" else "")),
            }
            rows.append({
                "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "format": fmt, "parameters": count, "payload_bytes": len(payload.encode()),
                "median_seconds": median, "iqr_seconds": iqr, "loops_per_sample": loops,
                "samples": samples, "warmups": warmups, "target_ms": target_ms,
                "python_version": platform.python_version(),
                "platform": platform_label(),
                "implementation": labels[fmt], "snt_version": scinumtools3.__version__,
                "snt_source": snt_source, "snt_local_revision": snt_local_revision,
                "snt_local_diff_sha256": snt_local_diff,
                "pydantic_version": __import__('pydantic').__version__,
                "pyyaml_version": yaml.__version__, "pint_version": __import__('pint').__version__,
                "matplotlib_version": matplotlib.__version__,
                "invalid_cases_checked": invalid_cases_checked,
                "status": "PASS",
            })

    output_dir = Path(get("execution.outputs.results_dir"))
    if not output_dir.is_absolute():
        output_dir = REPO_DIR / output_dir
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or output_dir / f"typed_config_{snt_source}_{stamp}.csv"
    figure = args.figure or output.with_suffix(".png")
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    plot(rows, figure, get("execution.outputs.figure_dpi"))
    workload_fields = (
        "name", "default_label", "name_pattern", "mode", "allowed_modes", "steps",
        "minimum_steps", "maximum_steps", "minimum_grid_count", "minimum_timestep",
        "minimum_grid_spacing", "timestep", "grid_nx", "grid_ny", "grid_spacing_m",
        "parameter_prefix", "parameter_digits", "value_period", "value_divisor",
    )
    config_text = args.config.resolve().read_text(encoding="utf-8")
    snapshot = {
        "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "config_path": path_label(args.config.resolve(), REPO_DIR),
        "config_sha256": hashlib.sha256(config_text.encode()).hexdigest(),
        "formats": formats,
        "parameter_counts": sizes,
        "timing": {"samples": samples, "warmups": warmups, "target_ms": target_ms,
                   "max_loops": max_loops},
        "workload": {key: get(f"workload.model.{key}") for key in workload_fields},
        "packages": {"scinumtools3": scinumtools3.__version__,
                     "pydantic": __import__('pydantic').__version__,
                     "pyyaml": yaml.__version__, "pint": __import__('pint').__version__,
                     "matplotlib": matplotlib.__version__},
        "snt_source": snt_source,
        "snt_local_revision": snt_local_revision,
        "snt_local_worktree_status": snt_local_status,
        "snt_local_diff_sha256": snt_local_diff,
        "python_version": platform.python_version(),
        "platform": platform_label(),
    }
    output.with_suffix(".config.json").write_text(
        json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(f"CSV: {output}\nFigure: {figure}")
    for row in rows:
        print(f"{row['format']:>5} {row['parameters']:>6} parameters: "
              f"{row['median_seconds'] * 1e3:9.3f} ms ({row['status']})")


if __name__ == "__main__":
    main()
