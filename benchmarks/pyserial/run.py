"""Create the pinned environment and run the DIPL-controlled parsing comparison."""

import argparse
import ast
from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


HERE = Path(__file__).resolve().parent
REPO_DIR = HERE.parents[1]
DEFAULT_CONFIG = HERE / "config.dip"
DIST_NAMES = {"scinumtools3": "scinumtools3", "pyyaml": "PyYAML"}


def as_list(value):
    return value if isinstance(value, list) else [value]


def literal_string(source, path):
    """Read bootstrap strings before the selected interpreter has SNT3 installed."""
    parents = []
    for line in source.splitlines():
        match = re.fullmatch(r'( *)([a-z_][a-z0-9_]*)(?: str = (".*"))?', line)
        if not match:
            continue
        indent, name, value = match.groups()
        while parents and parents[-1][0] >= len(indent):
            parents.pop()
        qualified = ".".join([node for _, node in parents] + [name])
        if value is not None:
            if qualified == path:
                return ast.literal_eval(value)
        else:
            parents.append((len(indent), name))
    raise ValueError(f"DIP configuration requires a literal {path} string")


def interpreter_path(value):
    found = shutil.which(str(value))
    if found is None:
        raise SystemExit(f"Python interpreter not found: {value}")
    return str(Path(found).absolute())


def pip_install(python_bin, requirements):
    print("Installing pinned packages: " + ", ".join(requirements), flush=True)
    subprocess.run([python_bin, "-m", "pip", "install", *requirements], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--python", help="Use a prepared interpreter without installing packages")
    parser.add_argument("--size", action="append", type=int, help="Parameter count; repeat to select sizes")
    parser.add_argument("--format", action="append", choices=("json", "yaml", "toml", "dipl"))
    parser.add_argument("--samples", type=int)
    parser.add_argument("--warmups", type=int)
    parser.add_argument("--target-ms", type=float)
    parser.add_argument("--max-loops", type=int)
    parser.add_argument("--ready", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    config_path = args.config.resolve()
    config_text = config_path.read_text()
    pinned_snt = literal_string(config_text, "pyserial.packages.scinumtools3.version")
    base_python = literal_string(config_text, "pyserial.execution.environment.python_base")
    external_python = args.python is not None
    if external_python:
        python_bin = interpreter_path(args.python)
    else:
        python_bin = str(HERE / ".venv-pinned" / "bin" / "python")
        if not Path(python_bin).exists():
            subprocess.run([interpreter_path(base_python), "-m", "venv", str(HERE / ".venv-pinned")], check=True)

    if not args.ready:
        check = subprocess.run([python_bin, "-c", "import importlib.metadata as m; print(m.version('scinumtools3'))"],
                               capture_output=True, text=True)
        if check.returncode or check.stdout.strip() != pinned_snt:
            if external_python:
                raise SystemExit(f"{python_bin} needs scinumtools3=={pinned_snt}")
            pip_install(python_bin, [f"scinumtools3=={pinned_snt}"])
        os.execve(python_bin, [python_bin, __file__, *sys.argv[1:], "--ready"], os.environ.copy())

    from scinumtools3.dip import DIP

    dip = DIP()
    dip.add_file(config_path)
    values = dip.parse()

    def get(path):
        return values[f"pyserial.{path}"].value

    package_names = dict.fromkeys(
        path.split(".")[2] for path in values.select_paths("?pyserial.packages.")
        if path.endswith(".version")
    )
    projects = {name: {"version": get(f"packages.{name}.version"),
                       "website": get(f"packages.{name}.website")}
                for name in package_names}
    missing = []
    for name, detail in projects.items():
        distribution_name = DIST_NAMES.get(name, name)
        try:
            found = version(distribution_name)
        except PackageNotFoundError:
            found = None
        if found != detail["version"]:
            missing.append(f"{distribution_name}=={detail['version']}")
    if missing:
        if external_python:
            raise SystemExit(f"{python_bin} needs: {', '.join(missing)}")
        if os.environ.get("SNT_BENCH_PYSERIAL_DEPS_INSTALLED") == "1":
            raise SystemExit("Package versions still differ after installation: " + ", ".join(missing))
        pip_install(python_bin, missing)
        env = os.environ.copy()
        env["SNT_BENCH_PYSERIAL_DEPS_INSTALLED"] = "1"
        os.execve(python_bin, [python_bin, __file__, *sys.argv[1:]], env)

    results_dir = Path(get("execution.outputs.results_dir"))
    if not results_dir.is_absolute():
        results_dir = REPO_DIR / results_dir
    results_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = results_dir / f"pyserial_pinned_quick_{stamp}_{os.getpid()}"
    command = [python_bin, str(HERE / "benchmark.py"), "--config", str(config_path),
               "--output", str(base.with_suffix(".csv")), "--figure", str(base.with_suffix(".png"))]
    for size in args.size or ():
        command.extend(("--size", str(size)))
    for fmt in args.format or ():
        command.extend(("--format", fmt))
    for flag, value in (("--samples", args.samples), ("--warmups", args.warmups),
                        ("--target-ms", args.target_ms), ("--max-loops", args.max_loops)):
        if value is not None:
            command.extend((flag, str(value)))
    subprocess.run(command, check=True)

    settings = {
        "formats": args.format if args.format is not None else as_list(get("execution.selection.formats")),
        "parameter_counts": args.size if args.size is not None else as_list(get("execution.selection.parameter_counts")),
        "samples": args.samples if args.samples is not None else get("timing.quick.samples"),
        "warmups": args.warmups if args.warmups is not None else get("timing.quick.warmups"),
        "target_ms": args.target_ms if args.target_ms is not None else get("timing.quick.target_ms"),
        "max_loops": args.max_loops if args.max_loops is not None else get("timing.quick.max_loops"),
        "export_smallest": get("execution.outputs.export_smallest"),
        "documents_dir": get("execution.outputs.documents_dir"),
        "figure_dpi": get("execution.outputs.figure_dpi"),
        "experiment": {name: get(f"workload.experiment.{name}")
                       for name in ("name", "enabled", "iterations", "timestep")},
        "parameters": {name: get(f"workload.parameters.{name}")
                       for name in ("name_prefix", "name_min_digits", "value_period", "value_divisor")},
    }
    snapshot = {
        "config_path": str(config_path),
        "config_sha256": hashlib.sha256(config_text.encode()).hexdigest(),
        "settings": settings,
        "projects": projects,
        "provenance": {name: get(f"provenance.{name}")
                       for name in ("method_website", "json_website", "tomllib_website")},
        "command": command,
        "python": python_bin,
    }
    base.with_suffix(".config.json").write_text(json.dumps(snapshot, indent=2) + "\n")
    print(f"Configuration: {base.with_suffix('.config.json')}")


if __name__ == "__main__":
    main()
