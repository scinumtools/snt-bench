"""Repeated, correctness-checked comparisons of Python unit-array libraries."""

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from fnmatch import fnmatchcase
from importlib.metadata import distribution, version
import importlib.util
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

import astropy.units as au
import numpy as np
import pandas as pd
import pint
import pyperf
import unyt as uy

from benchmark_config import DEFAULT_CONFIG, as_list, source_settings


pre_parser = argparse.ArgumentParser(add_help=False)
pre_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
pre_args, _ = pre_parser.parse_known_args()
CONFIG_PATH = pre_args.config.resolve()
SNT_SOURCE, LOCAL_REPO = source_settings(CONFIG_PATH)
if SNT_SOURCE == "local":
    sys.path.insert(0, str(LOCAL_REPO / "build" / "python"))
import scinumtools3
from scinumtools3.dip import DIP

dip = DIP()
dip.add_file(CONFIG_PATH)
CONFIG = dip.parse()

def get(path):
    return CONFIG[f"pyunits.{path}"].value

def add_worker_args(cmd, args):
    cmd.extend(["--config", str(args.config.resolve())])
    cmd.append("--quick" if args.quick else "--pyperf-mode")
    cmd.extend(["--sizes", *(str(size) for size in args.sizes)])
    cmd.extend(["--input-start", str(args.input_start), "--input-stop", str(args.input_stop),
                "--quick-warmups", str(args.quick_warmups), "--quick-values", str(args.quick_values),
                "--quick-target-seconds", str(args.quick_target_seconds),
                "--quick-max-loops", str(args.quick_max_loops),
                "--rtol", str(args.rtol), "--atol", str(args.atol)])
    for pattern in args.case:
        cmd.extend(["--case", pattern])
    for library in args.library:
        cmd.extend(["--library", library])


runner = pyperf.Runner(
    metadata={"benchmark_suite": "snt-bench-pyunits-matrix"},
    add_cmdline_args=add_worker_args,
)
runner.argparser.set_defaults(
    processes=get("timing.pyperf.processes"), values=get("timing.pyperf.values"),
    warmups=get("timing.pyperf.warmups"), min_time=get("timing.pyperf.min_time"),
    quick=get("execution.target.mode") == "quick",
)
runner.argparser.description = __doc__
runner.argparser.add_argument("--csv-output", type=Path,
                              help="Summary CSV path (pyperf JSON is written with --output)")
runner.argparser.add_argument("--config", type=Path, default=CONFIG_PATH,
                              help="DIP configuration for benchmark settings")
runner.argparser.add_argument("--sizes", nargs="+", type=int,
                              default=as_list(get("execution.selection.sizes")))
mode_group = runner.argparser.add_mutually_exclusive_group()
mode_group.add_argument("--quick", dest="quick", action="store_true",
                        help="Use the single-process, short-sample timing loop")
mode_group.add_argument("--pyperf-mode", dest="quick", action="store_false",
                        help="Use repeated pyperf worker processes")
runner.argparser.add_argument("--skip-memory", action="store_true",
                              default=get("execution.checks.skip_memory"),
                              help="Skip fresh-process peak RSS construction probes")
runner.argparser.add_argument("--case", action="append", metavar="GLOB",
                              help="Run matching case IDs; repeat for multiple patterns")
runner.argparser.add_argument("--library", action="append",
                              choices=("snt", "pint", "unyt", "astropy"),
                              help="Run this library; repeat for multiple libraries")
runner.argparser.add_argument("--list-cases", action="store_true",
                              help="Print case IDs and exit")
runner.argparser.add_argument("--input-start", type=float, default=get("workloads.matrix.input_start"))
runner.argparser.add_argument("--input-stop", type=float, default=get("workloads.matrix.input_stop"))
runner.argparser.add_argument("--quick-warmups", type=int, default=get("timing.quick.warmups"))
runner.argparser.add_argument("--quick-values", type=int, default=get("timing.quick.values"))
runner.argparser.add_argument("--quick-target-seconds", type=float,
                              default=get("timing.quick.target_seconds"))
runner.argparser.add_argument("--quick-max-loops", type=int, default=get("timing.quick.max_loops"))
runner.argparser.add_argument("--rtol", type=float, default=get("execution.checks.relative_tolerance"))
runner.argparser.add_argument("--atol", type=float, default=get("execution.checks.absolute_tolerance"))
args = runner.parse_args()
if args.case is None:
    args.case = as_list(get("execution.selection.cases"))
if args.library is None:
    args.library = as_list(get("execution.selection.libraries"))
EXPECTED_SNT_VERSION = get("packages.snt.version")
if not args.sizes or any(n < 2 for n in args.sizes):
    runner.argparser.error("all sizes must be >= 2")
if len(set(args.sizes)) != len(args.sizes):
    runner.argparser.error("sizes must be unique")
if args.input_start <= 0 or args.input_stop < args.input_start:
    runner.argparser.error("input range must be positive and nondecreasing")
if args.quick_warmups < 0 or args.quick_values < 1 or args.quick_target_seconds <= 0 or args.quick_max_loops < 1:
    runner.argparser.error("invalid quick timing settings")
if args.rtol < 0 or args.atol < 0:
    runner.argparser.error("tolerances must be nonnegative")
if not args.quick and not args.output and not args.worker and not args.list_cases:
    runner.argparser.error("--output is required for the raw pyperf JSON results")

SNT_GIT_COMMIT = ""
SNT_GIT_DIRTY = ""
if SNT_SOURCE == "local":
    local_python_path = LOCAL_REPO / "build" / "python"
    if not list((local_python_path / "scinumtools3").glob("_snt*.*")):
        raise SystemExit(
            f"No built Python binding found in {local_python_path}; build the local checkout first"
        )
    active_spec = importlib.util.find_spec("scinumtools3")
    if active_spec is None or not Path(active_spec.origin).resolve().is_relative_to(local_python_path.resolve()):
        raise SystemExit(f"SciNumTools3 import is not coming from {local_python_path}")
    try:
        SNT_GIT_COMMIT = subprocess.check_output(
            ["git", "-C", str(LOCAL_REPO), "rev-parse", "HEAD"], text=True
        ).strip()
        SNT_GIT_DIRTY = str(bool(subprocess.check_output(
            ["git", "-C", str(LOCAL_REPO), "status", "--porcelain"], text=True
        ).strip())).lower()
    except (OSError, subprocess.CalledProcessError):
        SNT_GIT_COMMIT = "unknown"
        SNT_GIT_DIRTY = "unknown"
else:
    snt_dist = distribution("scinumtools3")
    if snt_dist.version != EXPECTED_SNT_VERSION:
        raise SystemExit(f"Expected PyPI scinumtools3 {EXPECTED_SNT_VERSION}, found {snt_dist.version}")
    installed_init = Path(snt_dist.locate_file("scinumtools3/__init__.py")).resolve()
    active_spec = importlib.util.find_spec("scinumtools3")
    if active_spec is None or Path(active_spec.origin).resolve() != installed_init:
        raise SystemExit("SciNumTools3 import is not coming from the installed PyPI package")

from scinumtools3.puq import Quantity

SNT_VERSION = scinumtools3.__version__
if SNT_SOURCE == "pypi" and SNT_VERSION != EXPECTED_SNT_VERSION:
    raise SystemExit(f"Expected SciNumTools3 binding {EXPECTED_SNT_VERSION}, found {SNT_VERSION}")
installed_init = Path(scinumtools3.__file__).resolve()

ureg = pint.UnitRegistry()
LIBRARIES = ("snt", "pint", "unyt", "astropy")
LIBRARY_VERSIONS = {
    "snt": SNT_VERSION,
    "pint": version("pint"),
    "unyt": version("unyt"),
    "astropy": version("astropy"),
    "numpy": version("numpy"),
    "pyperf": pyperf.__version__,
}
RUN_UTC = datetime.now(timezone.utc).isoformat(timespec="seconds")
UNSUPPORTED = {}


@dataclass(frozen=True)
class Case:
    group: str
    operation: str
    input_kind: str
    elements: int

    @property
    def id(self):
        return f"{self.group}/{self.operation}/{self.input_kind}/{self.elements}"


def cases():
    yield Case("construction", "attach_units", "scalar", 1)
    for n in args.sizes:
        yield Case("construction", "attach_units", "list", n)
        yield Case("construction", "attach_units", "ndarray", n)

    for n in (1, *args.sizes):
        kind = "scalar" if n == 1 else "ndarray"
        for operation in ("same", "scaled", "compound", "temperature"):
            yield Case("conversion", operation, kind, n)
        for operation in ("add_equal", "add_compatible", "subtract_equal",
                          "multiply", "divide", "square", "sqrt"):
            yield Case("arithmetic", operation, kind, n)
        if n > 1:
            for operation in ("np_add", "np_sqrt", "np_sum"):
                yield Case("numpy", operation, kind, n)


all_cases = list(cases())
if args.list_cases:
    print("\n".join(case.id for case in all_cases))
    raise SystemExit(0)
selected_cases = [case for case in all_cases if not args.case or
                  any(fnmatchcase(case.id, pattern) for pattern in args.case)]
if not selected_cases:
    runner.argparser.error("--case did not match any case ID; use --list-cases")
if args.case:
    unmatched = [pattern for pattern in args.case if not any(
        fnmatchcase(case.id, pattern) for case in all_cases)]
    if unmatched:
        runner.argparser.error(f"unmatched --case pattern(s): {', '.join(unmatched)}")
selected_libraries = tuple(library for library in LIBRARIES if
                           not args.library or library in args.library)
if not selected_libraries:
    runner.argparser.error("no supported libraries selected")


def unit_name(library, unit):
    if unit == "degC":
        return {"snt": "Cel", "astropy": "deg_C"}.get(library, "degC")
    if unit == "km/h" and library == "unyt":
        return "km/hr"
    if unit == "m2" and library in ("pint", "unyt"):
        return "m**2"
    return unit


def make(library, data, unit):
    unit = unit_name(library, unit)
    if library == "snt":
        return Quantity(data, unit)
    if library == "pint":
        return ureg.Quantity(data, unit)
    if library == "unyt":
        return uy.unyt_array(data, unit) if isinstance(data, (list, np.ndarray)) else uy.unyt_quantity(data, unit)
    if library == "astropy":
        return au.Quantity(data, au.Unit(unit))
    raise ValueError(library)


def convert(library, quantity, unit):
    if unit == "sqrt_m":
        unit = {"pint": ureg.meter ** 0.5, "unyt": uy.meter ** 0.5,
                "astropy": au.m ** 0.5}[library]
    else:
        unit = unit_name(library, unit)
    if library == "snt":
        return quantity.convert(unit)
    if library == "astropy" and unit == "K":
        return quantity.to(unit, equivalencies=au.temperature())
    return quantity.to(unit)


def magnitude(library, quantity, scalar=False):
    if library == "snt":
        return quantity.value() if scalar else quantity.value(numpy=True)
    if library == "pint":
        return quantity.magnitude
    return quantity.value


def prepare(case, library, raw):
    data = float(raw[0]) if case.input_kind == "scalar" else raw
    if case.group == "construction":
        source = raw.tolist() if case.input_kind == "list" else data
        return lambda: make(library, source, "m"), data if case.input_kind == "scalar" else raw, "m"

    if case.group == "conversion":
        source_unit = "degC" if case.operation == "temperature" else "m/s" if case.operation == "compound" else "m"
        target = {"same": "m", "scaled": "mm", "compound": "km/h", "temperature": "K"}[case.operation]
        quantity = make(library, data, source_unit)
        expected = {"same": data, "scaled": data * 1_000,
                    "compound": data * 3.6, "temperature": data + 273.15}[case.operation]
        return lambda: convert(library, quantity, target), expected, target

    if case.operation in ("sqrt", "np_sqrt"):
        quantity = make(library, data * data, "m2")
        if library == "snt" and case.operation == "sqrt":
            from scinumtools3.puq import sqrt
            operation = lambda: sqrt(quantity)
        elif case.operation == "sqrt":
            operation = lambda: quantity ** 0.5
        else:
            operation = lambda: np.sqrt(quantity)
        return operation, data, "m"
    if case.operation == "np_sum":
        quantity = make(library, data, "m")
        return lambda: np.sum(quantity), float(np.sum(data)), "m"

    left = make(library, data, "m")
    if case.operation in ("add_equal", "np_add"):
        right = make(library, data * 2, "m")
        operation = (lambda: left + right) if case.operation == "add_equal" else (lambda: np.add(left, right))
        return operation, data * 3, "m"
    if case.operation == "add_compatible":
        right = make(library, data * 100, "cm")
        return lambda: left + right, data * 2, "m"
    if case.operation == "subtract_equal":
        right = make(library, data * 0.25, "m")
        return lambda: left - right, data * 0.75, "m"
    if case.operation == "multiply":
        right = make(library, data, "s")
        return lambda: left * right, data * data, "m*s"
    if case.operation == "divide":
        right = make(library, data * 0.5, "s")
        return lambda: left / right, np.full_like(data, 2.0) if isinstance(data, np.ndarray) else 2.0, "m/s"
    if case.operation == "square":
        return lambda: left * left, data * data, "m2"
    raise ValueError(case)


def numpy_baseline(case, raw):
    data = float(raw[0]) if case.input_kind == "scalar" else raw
    if case.group == "construction":
        source = raw.tolist() if case.input_kind == "list" else data
        return lambda: np.asarray(source, dtype=np.float64)
    if case.group == "conversion":
        return {
            "same": lambda: np.array(data, copy=True),
            "scaled": lambda: data * 1_000,
            "compound": lambda: data * 3.6,
            "temperature": lambda: data + 273.15,
        }[case.operation]
    if case.operation in ("sqrt", "np_sqrt"):
        return lambda: np.sqrt(data)
    if case.operation == "np_sum":
        return lambda: np.sum(data)
    if case.operation in ("add_equal", "np_add"):
        right = data * 2
        return lambda: np.add(data, right)
    if case.operation == "add_compatible":
        right_cm = data * 100
        return lambda: np.add(data, right_cm * 0.01)
    if case.operation == "subtract_equal":
        right = data * 0.25
        return lambda: np.subtract(data, right)
    if case.operation == "multiply":
        return lambda: np.multiply(data, data)
    if case.operation == "divide":
        right = data * 0.5
        return lambda: np.divide(data, right)
    if case.operation == "square":
        return lambda: np.square(data)
    raise ValueError(case)


def check_values(label, actual, expected):
    actual = np.asarray(actual, dtype=np.float64)
    expected = np.asarray(expected, dtype=np.float64)
    if actual.shape != expected.shape:
        raise AssertionError(f"{label}: shape {actual.shape} != {expected.shape}")
    np.testing.assert_allclose(actual, expected, rtol=args.rtol, atol=args.atol, err_msg=label)
    return float(np.max(np.abs(actual - expected)))


def summarize(samples):
    q1, q3 = np.percentile(samples, [25, 75])
    return {
        "median_seconds": statistics.median(samples),
        "iqr_seconds": float(q3 - q1),
        "min_seconds": min(samples),
        "max_seconds": max(samples),
    }


def measure_quick(operation):
    """Legacy short timing loop for rapid local development checks."""
    warmups = args.quick_warmups
    sample_count = args.quick_values
    target_seconds = args.quick_target_seconds
    for _ in range(warmups):
        operation()
    start = time.perf_counter_ns()
    operation()
    probe_ns = max(time.perf_counter_ns() - start, 1)
    loops = max(1, min(args.quick_max_loops, int(target_seconds * 1_000_000_000 / probe_ns)))
    samples = []
    for _ in range(sample_count):
        start = time.perf_counter_ns()
        for _ in range(loops):
            operation()
        samples.append((time.perf_counter_ns() - start) / loops / 1e9)
    return samples, loops


rows = []
sample_rows = []
benchmarks = []
for case_index, case in enumerate(selected_cases):
    raw = np.linspace(args.input_start, args.input_stop, case.elements, dtype=np.float64)
    baseline = numpy_baseline(case, raw)
    if args.quick:
        baseline_samples, baseline_loops = measure_quick(baseline)
        baseline_bench = None
    else:
        baseline_bench = runner.bench_func(
            f"{case.id}/numpy", baseline,
            metadata={"case_id": case.id, "library": "numpy"},
        )
        baseline_samples = baseline_bench.get_values() if baseline_bench is not None else []
        baseline_loops = None
    if args.quick or (baseline_bench is not None and not args.worker):
        if baseline_bench is not None:
            benchmarks.append((case, "numpy", baseline_bench))
        baseline_median = statistics.median(baseline_samples)
        sample_index = 0
        if args.quick:
            baseline_runs = [(0, baseline_loops, baseline_samples)]
        else:
            baseline_runs = [
                (run_index, run.get_metadata().get("loops"), run.values)
                for run_index, run in enumerate(baseline_bench.get_runs())
            ]
        for run_index, loops, values in baseline_runs:
            for seconds in values:
                sample_rows.append({"run_utc": RUN_UTC, "case_id": case.id, "library": "numpy",
                                    "library_version": LIBRARY_VERSIONS["numpy"],
                                    "pyperf_version": None if args.quick else pyperf.__version__,
                                    "measurement_method": "quick" if args.quick else "pyperf",
                                    "sample_index": sample_index, "run_index": run_index,
                                    "snt_source": SNT_SOURCE, "snt_git_commit": SNT_GIT_COMMIT,
                                    "snt_git_dirty": SNT_GIT_DIRTY,
                                    "loops": loops, "seconds_per_iteration": seconds})
                sample_index += 1

    # Rotate library order across cases to reduce systematic order effects.
    offset = case_index % len(selected_libraries)
    library_order = selected_libraries[offset:] + selected_libraries[:offset]
    if args.worker and not args.quick:
        for library in library_order:
            operation, _, _ = prepare(case, library, raw)
            runner.bench_func(
                f"{case.id}/{library}", operation,
                metadata={"case_id": case.id, "library": library},
            )
        continue

    for library in library_order:
        row = {
            "run_utc": RUN_UTC, "case_id": case.id, "group": case.group,
            "operation": case.operation, "input_kind": case.input_kind,
            "elements": case.elements, "library": library,
            "library_version": LIBRARY_VERSIONS[library],
            "scinumtools3_version": SNT_VERSION, "numpy_version": LIBRARY_VERSIONS["numpy"],
            "snt_source": SNT_SOURCE, "snt_git_commit": SNT_GIT_COMMIT,
            "snt_git_dirty": SNT_GIT_DIRTY,
            "python_version": platform.python_version(), "python_executable": sys.executable,
            "platform": platform.platform(), "architecture": platform.machine(),
            "snt_package_path": str(installed_init),
            "measurement_method": "quick" if args.quick else "pyperf",
            "pyperf_version": None if args.quick else pyperf.__version__,
            "processes": 1 if args.quick else args.processes,
            "values_per_process": args.quick_values if args.quick else args.values,
            "warmups": args.quick_warmups if args.quick else args.warmups,
            "minimum_sample_seconds": args.quick_target_seconds if args.quick else args.min_time,
            "numpy_median_seconds": baseline_median,
            "status": "UNSUPPORTED" if case.operation in UNSUPPORTED.get(library, ()) else "PASS",
            "shares_input": None, "peak_rss_delta_bytes": None,
            "max_absolute_error": None,
            "median_seconds": None, "iqr_seconds": None,
            "min_seconds": None, "max_seconds": None,
            "loops_per_sample": None, "overhead_vs_numpy": None,
        }
        if row["status"] == "PASS":
            operation, expected, target_unit = prepare(case, library, raw)
            result = operation()
            normalized = convert(library, result, target_unit)
            row["max_absolute_error"] = check_values(case.id + "/" + library,
                                                      magnitude(library, normalized,
                                                                scalar=case.input_kind == "scalar" or case.operation == "np_sum"),
                                                      expected)
            if case.group == "construction" and case.input_kind == "ndarray":
                public_array = result.to_numpy() if library == "snt" else magnitude(library, result)
                row["shares_input"] = bool(np.shares_memory(raw, public_array))
            if args.quick:
                samples, loops = measure_quick(operation)
                benchmark = None
            else:
                benchmark = runner.bench_func(
                    f"{case.id}/{library}", operation,
                    metadata={"case_id": case.id, "library": library},
                )
                if args.worker:
                    continue
                if benchmark is None:
                    continue
                benchmarks.append((case, library, benchmark))
                samples = benchmark.get_values()
            row.update(summarize(samples))
            row["loops_per_sample"] = str(loops) if args.quick else ";".join(
                str(run.get_metadata().get("loops", "")) for run in benchmark.get_runs()
            )
            row["overhead_vs_numpy"] = row["median_seconds"] / baseline_median
            sample_index = 0
            if args.quick:
                sample_runs = [(0, loops, samples)]
            else:
                sample_runs = [
                    (run_index, run.get_metadata().get("loops"), run.values)
                    for run_index, run in enumerate(benchmark.get_runs())
                ]
            for run_index, loops, values in sample_runs:
                for seconds in values:
                    sample_rows.append({"run_utc": RUN_UTC, "case_id": case.id, "library": library,
                                        "library_version": LIBRARY_VERSIONS[library],
                                        "pyperf_version": None if args.quick else pyperf.__version__,
                                        "measurement_method": "quick" if args.quick else "pyperf",
                                        "snt_source": SNT_SOURCE, "snt_git_commit": SNT_GIT_COMMIT,
                                        "snt_git_dirty": SNT_GIT_DIRTY,
                                        "run_index": run_index, "sample_index": sample_index,
                                        "loops": loops, "seconds_per_iteration": seconds})
                    sample_index += 1
        rows.append(row)

if not args.worker and not args.skip_memory:
    memory_probe = Path(__file__).with_name("memory_probe.py")
    for row in rows:
        if row["group"] != "construction":
            continue
        completed = subprocess.run(
            [sys.executable, str(memory_probe), row["library"], row["input_kind"],
             str(row["elements"]), "--config", str(args.config.resolve()),
             "--input-start", str(args.input_start),
             "--input-stop", str(args.input_stop)], check=True, capture_output=True, text=True
        )
        row["peak_rss_delta_bytes"] = json.loads(completed.stdout)["peak_rss_delta_bytes"]

if args.worker:
    raise SystemExit(0)

if not args.quick and not args.output:
    runner.argparser.error("pass --output PATH for the pyperf JSON results")
if args.csv_output is None and args.output:
    args.csv_output = Path(args.output).with_suffix(".csv")
if args.csv_output is None:
    runner.argparser.error("pass --csv-output PATH")

df = pd.DataFrame.from_records(rows)
passed = df["status"] == "PASS"
df["performance_rank"] = pd.Series(pd.NA, index=df.index, dtype="Int64")
df.loc[passed, "performance_rank"] = (
    df.loc[passed].groupby("case_id")["median_seconds"]
    .rank(method="min", ascending=True).astype("Int64")
)
df["_case_order"] = df["case_id"].map({case.id: i for i, case in enumerate(selected_cases)})
df = df.sort_values(["_case_order", "performance_rank", "library"], na_position="last")
df = df.drop(columns="_case_order")

args.csv_output.parent.mkdir(parents=True, exist_ok=True)
samples_output = args.csv_output.with_name(args.csv_output.stem + "_samples.csv")
df.to_csv(args.csv_output, index=False, float_format="%.12g")
pd.DataFrame.from_records(sample_rows).to_csv(samples_output, index=False, float_format="%.12g")

display = df.copy()
display["cell"] = display.apply(
    lambda row: f"{row['median_seconds'] * 1e6:.3f} ({int(row['performance_rank'])})"
    if row["status"] == "PASS" else "n/a", axis=1
)
table = display.pivot(index=["group", "operation", "input_kind", "elements", "numpy_median_seconds"],
                      columns="library", values="cell").reset_index()
table["numpy_median_seconds"] *= 1e6
table["_case_order"] = table.apply(
    lambda row: f"{row['group']}/{row['operation']}/{row['input_kind']}/{row['elements']}", axis=1
).map({case.id: i for i, case in enumerate(selected_cases)})
table = table.sort_values("_case_order").drop(columns="_case_order")
table = table.rename(columns={
    "group": "Group", "operation": "Operation", "input_kind": "Input",
    "elements": "Elements", "numpy_median_seconds": "NumPy (us)",
    **{name: f"{name} {LIBRARY_VERSIONS[name]}" for name in LIBRARIES},
})
table = table[["Group", "Operation", "Input", "Elements", "NumPy (us)",
               *(f"{name} {LIBRARY_VERSIONS[name]}" for name in selected_libraries)]]
print(f"Python {platform.python_version()}")
print(table.to_string(index=False, formatters={"NumPy (us)": "{:.3f}".format}))
print("Library cells: median microseconds (performance rank); n/a = unsupported.")
print(f"All timed library cases passed value, unit, and shape checks (rtol={args.rtol:g}, atol={args.atol:g}).")
if not args.skip_memory and (df["group"] == "construction").any():
    memory = df[df["group"] == "construction"].pivot(
        index=["input_kind", "elements"], columns="library", values="peak_rss_delta_bytes"
    ).reset_index()
    memory["_kind_order"] = memory["input_kind"].map({"scalar": 0, "list": 1, "ndarray": 2})
    memory = memory.sort_values(["elements", "_kind_order"]).drop(columns="_kind_order")
    for library in selected_libraries:
        memory[library] = memory[library] / 2**20
    memory = memory[["input_kind", "elements", *selected_libraries]]
    print("Construction: extra peak resident memory in a fresh process (MiB)")
    print(memory.to_string(index=False, formatters={name: "{:.2f}".format for name in selected_libraries}))
print("shares_input reports whether the public array aliases the input NumPy array.")
print(f"Summary CSV: {args.csv_output}")
print(f"Raw samples CSV: {samples_output}")
if not args.quick:
    print(f"Raw pyperf JSON: {args.output}")
