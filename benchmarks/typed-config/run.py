"""Prepare the pinned Python environment and run the typed-configuration comparison."""

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
PACKAGES = ("scinumtools3", "pydantic", "pyyaml", "pint", "matplotlib")
DIST_NAMES = {"scinumtools3": "scinumtools3", "pydantic": "pydantic",
              "pyyaml": "PyYAML", "pint": "Pint", "matplotlib": "matplotlib"}


def literal_string(source, path):
    parents = []
    for line in source.splitlines():
        match = re.fullmatch(r'( *)([a-z_][a-z0-9_]*)(?: str = (".*"))?', line)
        if not match:
            continue
        indent, name, value = match.groups()
        while parents and parents[-1][0] >= len(indent):
            parents.pop()
        qualified = ".".join([item[1] for item in parents] + [name])
        if value is not None:
            if qualified == path:
                return ast.literal_eval(value)
        else:
            parents.append((len(indent), name))
    raise ValueError(f"Missing string setting {path} in config.dip")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--python", help="Use an existing prepared interpreter")
    parser.add_argument("--source", choices=("pinned", "local"),
                        help="SNT3 source: pinned package or configured local checkout")
    parser.add_argument("--size", action="append", type=int)
    parser.add_argument("--format", action="append", choices=("json", "yaml", "toml", "dipl"))
    parser.add_argument("--samples", type=int)
    args = parser.parse_args()

    config = args.config.resolve()
    source = config.read_text(encoding="utf-8")
    snt_source = args.source or literal_string(source, "typed_config.execution.target.source")
    base_key = ("python_base" if snt_source == "pinned" else "local_python_base")
    base_python = literal_string(source, f"typed_config.execution.environment.{base_key}")
    local_repo = Path(literal_string(source, "typed_config.execution.paths.local_repo"))
    if not local_repo.is_absolute():
        local_repo = (REPO_DIR / local_repo).resolve()
    env = os.environ.copy()
    local_status = []
    if snt_source == "local":
        binding = local_repo / "build" / "python"
        if not list((binding / "scinumtools3").glob("_snt*.*")):
            raise SystemExit(f"Build the local SNT3 Python binding first: {binding}")
        env["PYTHONPATH"] = os.pathsep.join(filter(None, (str(binding), env.get("PYTHONPATH"))))
        env["SNT_BENCH_SOURCE"] = "local"
        local_revision = subprocess.run(
            ["git", "-C", str(local_repo), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True).stdout.strip()
        local_status = subprocess.run(
            ["git", "-C", str(local_repo), "status", "--short"],
            check=True, capture_output=True, text=True).stdout.splitlines()
        local_diff = subprocess.run(
            ["git", "-C", str(local_repo), "diff", "HEAD", "--binary"],
            check=True, capture_output=True).stdout
        env["SNT_BENCH_LOCAL_REVISION"] = local_revision
        env["SNT_BENCH_LOCAL_DIFF_SHA256"] = hashlib.sha256(local_diff).hexdigest()
        env["SNT_BENCH_LOCAL_STATUS"] = json.dumps(local_status)
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

    checked_packages = PACKAGES if snt_source == "pinned" else PACKAGES[1:]
    requirements = [f"{name}=={literal_string(source, f'typed_config.packages.{name}.version')}"
                    for name in checked_packages]
    missing = []
    for name in checked_packages:
        check = subprocess.run(
            [python, "-c", "import importlib.metadata as m,sys; print(m.version(sys.argv[1]))",
            DIST_NAMES[name]], capture_output=True, text=True, env=env,
        )
        expected = literal_string(source, f"typed_config.packages.{name}.version")
        if check.returncode or check.stdout.strip() != expected:
            missing.append(f"{DIST_NAMES[name]}=={expected}")
    if missing:
        if args.python is not None:
            raise SystemExit(f"{python} needs: {', '.join(missing)}")
        subprocess.run([python, "-m", "pip", "install", *requirements], check=True, env=env)
    if snt_source == "local":
        check = subprocess.run(
            [python, "-c", "import scinumtools3; print(scinumtools3.__version__)"],
            capture_output=True, text=True, env=env,
        )
        if check.returncode:
            raise SystemExit(f"Local SNT3 binding cannot be imported by {python}: {check.stderr.strip()}")

    command = [python, str(HERE / "benchmark.py"), "--config", str(config)]
    for size in args.size or ():
        command.extend(("--size", str(size)))
    for fmt in args.format or ():
        command.extend(("--format", fmt))
    if args.samples is not None:
        command.extend(("--samples", str(args.samples)))
    subprocess.run(command, check=True, env=env)

    sys.path.insert(0, str(REPO_DIR / "benchmarks"))
    from result_retention import prune_old_results

    output_dir = Path(literal_string(source, "typed_config.execution.outputs.results_dir"))
    if not output_dir.is_absolute():
        output_dir = REPO_DIR / output_dir
    prune_old_results(output_dir, keep=10)


if __name__ == "__main__":
    main()
