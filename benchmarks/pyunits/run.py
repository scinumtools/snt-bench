"""Bootstrap and run the pyunits benchmarks from the DIPL configuration."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from benchmark_config import as_list, literal_string, pinned_snt_version


BENCH_DIR = Path(__file__).resolve().parent
REPO_DIR = BENCH_DIR.parents[1]
DIST_NAMES = {"snt": "scinumtools3"}


def interpreter_path(value):
    found = shutil.which(value)
    if found is None:
        raise SystemExit(f"Python interpreter not found: {value}")
    # Resolving the venv's python symlink would bypass its site-packages.
    return str(Path(found).absolute())


def pip_install(python_bin, requirements):
    print("Installing pinned packages: " + ", ".join(requirements), flush=True)
    subprocess.run([python_bin, "-m", "pip", "install", *requirements], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-b", "--benchmark", choices=("pyunits", "pyunits-basic"))
    parser.add_argument("--source", "--snt-source", choices=("pinned", "pypi", "local"))
    parser.add_argument("--mode", choices=("quick", "pyperf"))
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--quick", action="store_const", const="quick", dest="mode_alias")
    mode_group.add_argument("--pyperf", action="store_const", const="pyperf", dest="mode_alias")
    parser.add_argument("--case", action="append", metavar="GLOB", help="Rerun matching case IDs")
    parser.add_argument("--library", action="append", choices=("snt", "pint", "unyt", "astropy", "sympy"))
    parser.add_argument("--size", action="append", type=int, metavar="N")
    parser.add_argument("--skip-memory", action="store_true", default=None)
    parser.add_argument("--processes", type=int)
    parser.add_argument("--values", type=int)
    parser.add_argument("--warmups", type=int)
    parser.add_argument("--min-time", type=float)
    parser.add_argument("--python", help="Use an existing environment without installing packages")
    parser.add_argument("--config", type=Path, default=BENCH_DIR / "config.dip")
    parser.add_argument("--list-cases", action="store_true")
    parser.add_argument("--ready", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    config_path = args.config.resolve()
    config_text = config_path.read_text()
    source = args.source or literal_string(config_text, "pyunits.execution.target.source")
    source = "pinned" if source == "pypi" else source
    if source not in ("pinned", "local"):
        parser.error("run.source must be pinned or local")
    local_repo = Path(os.environ.get("SNT_LOCAL_REPO", literal_string(config_text, "pyunits.execution.paths.local_repo")))
    if not local_repo.is_absolute():
        local_repo = (REPO_DIR / local_repo).resolve()

    env = os.environ.copy()
    env["SNT_SOURCE"] = "pypi" if source == "pinned" else "local"
    if source == "local":
        binding = local_repo / "build" / "python"
        if not list((binding / "scinumtools3").glob("_snt*.*")):
            raise SystemExit(f"Build the local Python binding first: {binding}")
        env["SNT_LOCAL_REPO"] = str(local_repo)
        env["PYTHONPATH"] = str(binding)
        venv_dir = BENCH_DIR / ".venv-local"
        base_python = local_repo / literal_string(config_text, "pyunits.execution.paths.local_base_python")
    else:
        env.pop("PYTHONPATH", None)
        venv_dir = BENCH_DIR / ".venv-pinned"
        base_python = os.environ.get("PYTHON_BASE", literal_string(config_text, "pyunits.execution.paths.python_base"))

    override = args.python or os.environ.get("PYTHON")
    external_python = override is not None
    if external_python:
        python_bin = interpreter_path(override)
    else:
        python_bin = str(venv_dir / "bin" / "python")
        if not Path(python_bin).exists():
            subprocess.run([interpreter_path(str(base_python)), "-m", "venv", str(venv_dir)], check=True)

    if not args.ready:
        if source == "pinned":
            # Query the selected interpreter, not the Python launching this file.
            check = subprocess.run([python_bin, "-c", "import importlib.metadata as m; print(m.version('scinumtools3'))"],
                                   capture_output=True, text=True, env=env)
            required_snt = pinned_snt_version(config_path)
            if check.returncode or check.stdout.strip() != required_snt:
                if external_python:
                    raise SystemExit(f"{python_bin} needs scinumtools3=={required_snt}")
                pip_install(python_bin, [f"scinumtools3=={required_snt}"])
        os.execve(python_bin, [python_bin, __file__, *sys.argv[1:], "--ready"], env)

    from importlib.metadata import PackageNotFoundError, version
    from scinumtools3.dip import DIP

    dip = DIP()
    dip.add_file(config_path)
    values = dip.parse()

    def get(path):
        return values[f"pyunits.{path}"].value
    package_names = dict.fromkeys(
        path.split(".")[2] for path in values.select_paths("?pyunits.packages.")
        if path.endswith(".version")
    )
    projects = {name: {"version": get(f"packages.{name}.version"),
                       "website": get(f"packages.{name}.website")}
                for name in package_names}
    required = {DIST_NAMES.get(name, name): detail["version"]
                for name, detail in projects.items() if name != "snt" or source == "pinned"}
    missing = []
    for name, wanted in required.items():
        try:
            found = version(name)
        except PackageNotFoundError:
            found = None
        if found != wanted:
            missing.append(f"{name}=={wanted}")
    if missing:
        if external_python:
            raise SystemExit(f"{python_bin} needs: {', '.join(missing)}")
        if env.get("SNT_BENCH_DEPS_INSTALLED") == "1":
            raise SystemExit(f"Package versions still differ after installation: {', '.join(missing)}")
        pip_install(python_bin, missing)
        env["SNT_BENCH_DEPS_INSTALLED"] = "1"
        os.execve(python_bin, [python_bin, __file__, *sys.argv[1:]], env)

    benchmark = args.benchmark or get("execution.target.benchmark")
    mode = args.mode_alias or args.mode or get("execution.target.mode")
    if benchmark not in ("pyunits", "pyunits-basic") or mode not in ("quick", "pyperf"):
        parser.error("invalid run.benchmark or run.mode in config.dip")
    if benchmark == "pyunits-basic" and mode != "quick":
        parser.error("pyunits-basic has only its fixed single-run timing method")
    if benchmark == "pyunits-basic" and any((args.case, args.size, args.list_cases)):
        parser.error("case, size, and list-cases apply only to pyunits")

    settings = {
        "benchmark": benchmark, "source": source, "mode": mode,
        "sizes": args.size if args.size is not None else as_list(values["pyunits.execution.selection.sizes"].value),
        "cases": args.case if args.case is not None else as_list(get("execution.selection.cases")),
        "libraries": args.library if args.library is not None else as_list(get(
            "execution.selection.basic_libraries" if benchmark == "pyunits-basic"
            else "execution.selection.libraries")),
        "skip_memory": args.skip_memory if args.skip_memory is not None else get("execution.checks.skip_memory"),
        "relative_tolerance": get("execution.checks.relative_tolerance"),
        "absolute_tolerance": get("execution.checks.absolute_tolerance"),
        "input_start": get("workloads.matrix.input_start"), "input_stop": get("workloads.matrix.input_stop"),
        "quick_warmups": get("timing.quick.warmups"), "quick_values": get("timing.quick.values"),
        "quick_target_seconds": get("timing.quick.target_seconds"),
        "quick_max_loops": get("timing.quick.max_loops"),
        "processes": args.processes if args.processes is not None else get("timing.pyperf.processes"),
        "values": args.values if args.values is not None else get("timing.pyperf.values"),
        "warmups": args.warmups if args.warmups is not None else get("timing.pyperf.warmups"),
        "min_time": args.min_time if args.min_time is not None else get("timing.pyperf.min_time"),
        "scalar_m": get("workloads.basic.scalar_m"), "scalar_us_ft": get("workloads.basic.scalar_us_ft"),
        "scalar_loops": get("workloads.basic.scalar_loops"), "array_size": get("workloads.basic.array_size"),
        "array_seed": get("workloads.basic.array_seed"),
    }
    if benchmark == "pyunits" and "sympy" in settings["libraries"]:
        parser.error("SymPy is available only in pyunits-basic")
    if args.list_cases:
        subprocess.run([python_bin, str(BENCH_DIR / "matrix.py"), "--config", str(config_path),
                        "--list-cases", "--sizes",
                        *(str(n) for n in settings["sizes"])], check=True, env=env)
        return

    results_dir = Path(get("execution.paths.output_dir"))
    if not results_dir.is_absolute():
        results_dir = REPO_DIR / results_dir
    results_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = results_dir / f"{benchmark}_{source}_{mode}_{stamp}_{os.getpid()}"
    csv_output = base.with_suffix(".csv")
    if benchmark == "pyunits-basic":
        cmd = [python_bin, str(BENCH_DIR / "compare.py"), "--config", str(config_path),
               "--output", str(csv_output),
               "--scalar-m", str(settings["scalar_m"]), "--scalar-us-ft", str(settings["scalar_us_ft"]),
               "--scalar-loops", str(settings["scalar_loops"]), "--array-size", str(settings["array_size"]),
               "--array-seed", str(settings["array_seed"]), "--rtol", str(settings["relative_tolerance"]),
               "--atol", str(settings["absolute_tolerance"])]
        for library in settings["libraries"]:
            cmd.extend(("--library", library))
    else:
        cmd = [python_bin, str(BENCH_DIR / "matrix.py"), "--config", str(config_path),
               "--csv-output", str(csv_output),
               "--sizes", *(str(n) for n in settings["sizes"]),
               "--input-start", str(settings["input_start"]), "--input-stop", str(settings["input_stop"]),
               "--quick-warmups", str(settings["quick_warmups"]),
               "--quick-values", str(settings["quick_values"]),
               "--quick-target-seconds", str(settings["quick_target_seconds"]),
               "--quick-max-loops", str(settings["quick_max_loops"]),
               "--rtol", str(settings["relative_tolerance"]), "--atol", str(settings["absolute_tolerance"])]
        for pattern in settings["cases"]:
            cmd.extend(("--case", pattern))
        for library in settings["libraries"]:
            cmd.extend(("--library", library))
        if settings["skip_memory"]:
            cmd.append("--skip-memory")
        if mode == "quick":
            cmd.append("--quick")
        else:
            cmd.extend(("--pyperf-mode", "--output", str(base.with_suffix(".pyperf.json")),
                        "--processes", str(settings["processes"]), "--values", str(settings["values"]),
                        "--warmups", str(settings["warmups"]), "--min-time", str(settings["min_time"])))
    subprocess.run(cmd, check=True, env=env)
    figure = base.with_suffix(".png")
    subprocess.run([python_bin, str(BENCH_DIR / "plot_results.py"), "--input", str(csv_output),
                    "--output", str(figure)], check=True, env=env)
    snapshot = {
        "config_path": str(config_path),
        "config_sha256": hashlib.sha256(config_text.encode()).hexdigest(),
        "settings": settings, "projects": projects,
        "provenance": {"reference_revision": get("provenance.reference_revision"),
                       "reference_repository": get("provenance.reference_repository")},
        "command": cmd, "python": python_bin,
    }
    import scinumtools3
    snapshot["actual_snt"] = {"version": scinumtools3.__version__,
                              "package_path": str(Path(scinumtools3.__file__).resolve())}
    if source == "local":
        snapshot["actual_snt"]["git_commit"] = subprocess.check_output(
            ["git", "-C", str(local_repo), "rev-parse", "HEAD"], text=True).strip()
        snapshot["actual_snt"]["git_dirty"] = bool(subprocess.check_output(
            ["git", "-C", str(local_repo), "status", "--porcelain"], text=True).strip())
    base.with_suffix(".config.json").write_text(json.dumps(snapshot, indent=2) + "\n")
    print(f"Results: {csv_output}\nFigure: {figure}\nConfiguration: {base.with_suffix('.config.json')}")


if __name__ == "__main__":
    main()
