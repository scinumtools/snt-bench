"""Prepare the Python environment and run the schema-validation comparison."""

import argparse
import ast
import hashlib
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


def literal_string(source, wanted):
    parents = []
    for line in source.splitlines():
        match = re.fullmatch(r'( *)([a-z_][a-z0-9_]*)(?: str = (".*"))?', line)
        if not match:
            continue
        indent, name, value = match.groups()
        while parents and parents[-1][0] >= len(indent):
            parents.pop()
        path = ".".join([item[1] for item in parents] + [name])
        if value is not None and path == wanted:
            return ast.literal_eval(value)
        if value is None:
            parents.append((len(indent), name))
    raise ValueError(f"Missing string setting {wanted} in config.dip")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--python", help="Use a prepared interpreter; no packages are installed into it")
    parser.add_argument("--source", choices=("pinned", "local"),
                        help="SNT3 source for the in-process DIPL comparison")
    parser.add_argument("--method", choices=("cli", "inprocess"), default="cli",
                        help="Compare all native CLIs or the DIPL and JSON Schema Python APIs")
    parser.add_argument("--participant", action="append", choices=("dipl", "jsonschema", "cue", "pkl"))
    parser.add_argument("--samples", type=int)
    parser.add_argument("--list-cases", action="store_true")
    args = parser.parse_args()

    config = args.config.resolve()
    source = config.read_text(encoding="utf-8")
    snt_source = args.source or literal_string(source, "schema_validation.execution.target.source")
    base_key = "python_base" if snt_source == "pinned" else "local_python_base"
    base_python = literal_string(source, f"schema_validation.execution.environment.{base_key}")
    local_repo = Path(literal_string(source, "schema_validation.execution.local.repo"))
    if not local_repo.is_absolute():
        local_repo = (REPO_DIR / local_repo).resolve()
    env = os.environ.copy()
    if snt_source == "local":
        if args.method != "inprocess":
            raise SystemExit("--source local is supported for --method inprocess only")
        binding = local_repo / "build" / "python"
        if not list((binding / "scinumtools3").glob("_snt*.*")):
            raise SystemExit(f"Build the local SNT3 Python binding first: {binding}")
        env["PYTHONPATH"] = os.pathsep.join(filter(None, (str(binding), env.get("PYTHONPATH"))))
        env["SNT_BENCH_SOURCE"] = "local"
        env["SNT_BENCH_LOCAL_REVISION"] = subprocess.run(
            ["git", "-C", str(local_repo), "rev-parse", "HEAD"], check=True,
            capture_output=True, text=True).stdout.strip()
        status = subprocess.run(["git", "-C", str(local_repo), "status", "--short"],
                                check=True, capture_output=True, text=True).stdout.splitlines()
        diff = subprocess.run(["git", "-C", str(local_repo), "diff", "HEAD", "--binary"],
                              check=True, capture_output=True).stdout
        env["SNT_BENCH_LOCAL_STATUS"] = json.dumps(status)
        env["SNT_BENCH_LOCAL_DIFF_SHA256"] = hashlib.sha256(diff).hexdigest()
    if args.python:
        python = shutil.which(args.python)
        if python is None:
            raise SystemExit(f"Python interpreter not found: {args.python}")
    else:
        env_name = ".venv-pinned" if snt_source == "pinned" else ".venv-local"
        python = str(HERE / env_name / "bin" / "python")
        if not Path(python).exists():
            base = shutil.which(base_python)
            if base is None:
                raise SystemExit(f"Python interpreter not found: {base_python}")
            subprocess.run([base, "-m", "venv", str(HERE / env_name)], check=True)

    if args.list_cases:
        cases_file = HERE / "cases.json"
        for item in json.loads(cases_file.read_text(encoding="utf-8")):
            print(item["id"])
        return

    if args.python is None:
        requirements = []
        package_names = (("scinumtools3", "jsonschema", "numpy", "matplotlib")
                         if snt_source == "pinned" else ("jsonschema", "numpy", "matplotlib"))
        for name in package_names:
            requirements.append(name + "==" + literal_string(
                source, f"schema_validation.packages.{name}.version"))
        needs_install = False
        for name in package_names:
            check = subprocess.run([python, "-c",
                                    "import importlib.metadata as m,sys; "
                                    "print(m.version(sys.argv[1]))", name],
                                   capture_output=True, text=True)
            expected = literal_string(source, f"schema_validation.packages.{name}.version")
            if check.returncode or check.stdout.strip() != expected:
                needs_install = True
        if needs_install:
            subprocess.run([python, "-m", "pip", "install", *requirements], check=True)

    if args.method == "inprocess" and any(participant not in ("dipl", "jsonschema")
                                           for participant in args.participant or ()):
        raise SystemExit("The in-process method supports only --participant dipl and --participant jsonschema")
    script = "benchmark_inprocess.py" if args.method == "inprocess" else "benchmark.py"
    command = [python, str(HERE / script), "--config", str(config)]
    if args.samples is not None:
        command.extend(("--samples", str(args.samples)))
    for participant in args.participant or ():
        command.extend(("--participant", participant))
    subprocess.run(command, check=True, env=env)


if __name__ == "__main__":
    main()
