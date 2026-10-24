import argparse
from datetime import datetime, timezone
import timeit
import time
import platform
import importlib.util
from importlib.metadata import distribution, version
from pathlib import Path
import subprocess
import numpy as np
import pandas as pd
import sys

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

parser = argparse.ArgumentParser(description="Compare Python physical-unit libraries")
parser.add_argument("--output", required=True, type=Path, help="CSV results path")
parser.add_argument("--config", type=Path, default=CONFIG_PATH,
                    help="DIP configuration for benchmark settings")
parser.add_argument("--scalar-m", type=float, default=get("workloads.basic.scalar_m"))
parser.add_argument("--scalar-us-ft", type=float, default=get("workloads.basic.scalar_us_ft"))
parser.add_argument("--scalar-loops", type=int, default=get("workloads.basic.scalar_loops"))
parser.add_argument("--array-size", type=int, default=get("workloads.basic.array_size"))
parser.add_argument("--array-seed", type=int, default=get("workloads.basic.array_seed"))
parser.add_argument("--rtol", type=float, default=get("execution.checks.relative_tolerance"))
parser.add_argument("--atol", type=float, default=get("execution.checks.absolute_tolerance"))
parser.add_argument("--library", action="append", choices=("snt", "pint", "unyt", "astropy", "sympy"),
                    help="Time only this library; repeat to select several")
args = parser.parse_args()
selected_libraries = tuple(dict.fromkeys(args.library if args.library is not None else
                                        as_list(get("execution.selection.basic_libraries"))))
if not selected_libraries or set(selected_libraries) - {"snt", "pint", "unyt", "astropy", "sympy"}:
    parser.error("basic_libraries must contain supported libraries")
EXPECTED_SNT_VERSION = get("packages.snt.version")
if args.scalar_loops < 1 or args.array_size < 1 or args.rtol < 0 or args.atol < 0:
    parser.error("loops and array size must be positive; tolerances must be nonnegative")

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
        raise SystemExit("SciNumTools3 import is not coming from the installed PyPI package; check PYTHONPATH")

SNT_VERSION = scinumtools3.__version__
if SNT_SOURCE == "pypi" and SNT_VERSION != EXPECTED_SNT_VERSION:
    raise SystemExit(f"Expected SciNumTools3 binding {EXPECTED_SNT_VERSION}, found {SNT_VERSION}")
installed_init = Path(scinumtools3.__file__).resolve()

library_versions = {
    "snt": scinumtools3.__version__,
    "pint": version("pint"),
    "unyt": version("unyt"),
    "astropy": version("astropy"),
    "sympy": version("sympy"),
}
run_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
results = []


def record(workload, library, operation, iterations, elements, elapsed_seconds):
    results.append({
        "run_utc": run_utc,
        "workload": workload,
        "library": library,
        "operation": operation,
        "iterations": iterations,
        "elements_per_iteration": elements,
        "total_seconds": elapsed_seconds,
        "seconds_per_iteration": elapsed_seconds / iterations,
        "library_version": library_versions[library],
        "scinumtools3_version": scinumtools3.__version__,
        "numpy_version": version("numpy"),
        "pandas_version": pd.__version__,
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "architecture": platform.machine(),
        "snt_package_path": str(installed_init),
        "snt_source": SNT_SOURCE,
        "snt_git_commit": SNT_GIT_COMMIT,
        "snt_git_dirty": SNT_GIT_DIRTY,
    })

# ==========================================
# 1. SETUP CODES (Executed once per library)
# ==========================================
setup_snt = """
from scinumtools3.puq import Quantity
from scinumtools3.puq.systems import SystemType
"""

setup_pint = """
import pint
ureg = pint.UnitRegistry()
"""

setup_unyt = """
import unyt as u
"""

setup_astropy = """
import astropy.units as u
from astropy.units import imperial
"""

setup_sympy = """
from sympy.physics.units import meter, foot, inch, convert_to
"""

# ==========================================
# 2. SCALAR OPERATIONS (Math + Conversion)
# ==========================================
test_snt_scalar = f"""
q1 = Quantity({args.scalar_m},'m')
q2 = Quantity({args.scalar_us_ft},'US_ft')
res = (q1 + q2).convert('US_in')
"""

test_pint_scalar = f"""
q1 = {args.scalar_m} * ureg.meter
q2 = {args.scalar_us_ft} * ureg.foot
res = (q1 + q2).to(ureg.inch)
"""

test_unyt_scalar = f"""
q1 = {args.scalar_m} * u.meter
q2 = {args.scalar_us_ft} * u.foot
res = (q1 + q2).to(u.inch)
"""

test_astropy_scalar = f"""
q1 = {args.scalar_m} * u.meter
q2 = {args.scalar_us_ft} * imperial.foot
res = (q1 + q2).to(imperial.inch)
"""

test_sympy_scalar = f"""
q1 = {args.scalar_m} * meter
q2 = {args.scalar_us_ft} * foot
res = convert_to(q1 + q2, inch)
"""

# ==========================================
# 3. RUNNING SCALAR BENCHMARKS
# ==========================================
SCALAR_LOOPS = args.scalar_loops
scalar_tests = {
    "snt": (test_snt_scalar, setup_snt),
    "pint": (test_pint_scalar, setup_pint),
    "unyt": (test_unyt_scalar, setup_unyt),
    "astropy": (test_astropy_scalar, setup_astropy),
    "sympy": (test_sympy_scalar, setup_sympy),
}
for library in selected_libraries:
    statement, setup = scalar_tests[library]
    elapsed = timeit.timeit(stmt=statement, setup=setup, number=SCALAR_LOOPS)
    record("scalar", library, "add_and_convert", SCALAR_LOOPS, 1, elapsed)


# ==========================================
# 4. ARRAY OPERATIONS BENCHMARK (Macro performance)
# ==========================================
ARRAY_SIZE = args.array_size
raw_array = np.random.default_rng(args.array_seed).random(ARRAY_SIZE)

# SymPy has no NumPy-backed array quantity. Only selected libraries run.
from scinumtools3.puq import Quantity
import pint
import unyt as u
import astropy.units as au
ureg = pint.UnitRegistry()
array_tests = {
    "snt": lambda: Quantity(raw_array, "m").convert("mm"),
    "pint": lambda: (raw_array * ureg.meter).to(ureg.millimeter),
    "unyt": lambda: (raw_array * u.meter).to(u.millimeter),
    "astropy": lambda: (raw_array * au.meter).to(au.millimeter),
}
array_quantities = {}
for library in selected_libraries:
    if library not in array_tests:
        continue
    start = time.perf_counter()
    array_quantities[library] = array_tests[library]()
    record("array", library, "construct_and_convert", 1, ARRAY_SIZE,
           time.perf_counter() - start)

# Validate outside the timed regions. Scalar timing uses timeit statements,
# so evaluate each expression once more to inspect its final quantity.
from astropy.units import imperial
from sympy.physics.units import meter, foot, inch, convert_to

scalar_factories = {
    "snt": lambda: (Quantity(args.scalar_m, "m") + Quantity(args.scalar_us_ft, "US_ft")).convert("US_in"),
    "pint": lambda: (args.scalar_m * ureg.meter + args.scalar_us_ft * ureg.foot).to(ureg.inch),
    "unyt": lambda: (args.scalar_m * u.meter + args.scalar_us_ft * u.foot).to(u.inch),
    "astropy": lambda: (args.scalar_m * au.meter + args.scalar_us_ft * imperial.foot).to(imperial.inch),
    "sympy": lambda: convert_to(args.scalar_m * meter + args.scalar_us_ft * foot, inch),
}
scalar_quantities = {library: scalar_factories[library]() for library in selected_libraries}
scalar_unit_checks = {
    "snt": lambda quantity: quantity.units == "in",
    "pint": lambda quantity: quantity.units == ureg.inch,
    "unyt": lambda quantity: quantity.units == u.inch,
    "astropy": lambda quantity: quantity.unit == imperial.inch,
    "sympy": lambda quantity: True,  # Dividing by inch must leave a dimensionless number.
}
scalar_values = {
    "snt": lambda quantity: quantity.value(),
    "pint": lambda quantity: quantity.magnitude,
    "unyt": lambda quantity: quantity.value,
    "astropy": lambda quantity: quantity.value,
    "sympy": lambda quantity: float(quantity / inch),
}
unit_checks = {
    "scalar": {library: scalar_unit_checks[library](quantity)
               for library, quantity in scalar_quantities.items()},
    "array": {},
}
actual_values = {
    "scalar": {library: scalar_values[library](quantity)
               for library, quantity in scalar_quantities.items()},
    "array": {},
}
for library, quantity in array_quantities.items():
    if library == "snt":
        unit_checks["array"][library] = quantity.units == "mm"
        actual_values["array"][library] = quantity.value(numpy=True)
    elif library == "pint":
        unit_checks["array"][library] = quantity.units == ureg.millimeter
        actual_values["array"][library] = quantity.magnitude
    elif library == "unyt":
        unit_checks["array"][library] = quantity.units == u.millimeter
        actual_values["array"][library] = quantity.value
    else:
        unit_checks["array"][library] = quantity.unit == au.millimeter
        actual_values["array"][library] = quantity.value
expected_values = {
    "scalar": (args.scalar_m + args.scalar_us_ft * 0.3048) / 0.0254,
    "array": raw_array * 1000,
}

for row in results:
    workload = row["workload"]
    library = row["library"]
    if not unit_checks[workload][library]:
        raise AssertionError(f"{library} {workload}: unexpected output unit")
    actual = np.asarray(actual_values[workload][library], dtype=np.float64)
    expected = np.asarray(expected_values[workload], dtype=np.float64)
    np.testing.assert_allclose(actual, expected, rtol=args.rtol, atol=args.atol,
                               err_msg=f"{library} {workload} result differs")
    row["max_absolute_error"] = float(np.max(np.abs(actual - expected)))
    row["value_check"] = "PASS"

df = pd.DataFrame.from_records(results)
df["performance_rank"] = (
    df.groupby("workload")["seconds_per_iteration"]
    .rank(method="min", ascending=True)
    .astype(int)
)
df["_workload_order"] = df["workload"].map({"scalar": 0, "array": 1})
df = df.sort_values(["_workload_order", "performance_rank", "library"])
df = df.drop(columns="_workload_order")
args.output.parent.mkdir(parents=True, exist_ok=True)
df.to_csv(args.output, index=False, float_format="%.12g")

table = df[["workload", "performance_rank", "library", "library_version", "iterations", "elements_per_iteration", "total_seconds", "seconds_per_iteration", "value_check"]].copy()
table.columns = ["Workload", "Rank", "Library", "Version", "Iterations", "Elements", "Total (s)", "Per iteration (ms)", "Check"]
table["Per iteration (ms)"] *= 1000
print(f"Python {platform.python_version()}")
print(table.to_string(index=False, formatters={
    "Total (s)": "{:.6f}".format,
    "Per iteration (ms)": "{:.6f}".format,
}))
print(f"Value check: all results match expected inches or millimeters (rtol={args.rtol:g}, atol={args.atol:g}).")
if "sympy" in selected_libraries:
    print("SymPy is excluded from the NumPy-backed array workload.")
