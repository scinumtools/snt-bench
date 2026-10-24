"""Prepare the Python environment and run the schema-validation comparison."""

import argparse
import ast
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


HERE = Path(__file__).resolve().parent
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
    parser.add_argument("--participant", action="append", choices=("dipl", "jsonschema", "cue", "pkl"))
    parser.add_argument("--samples", type=int)
    parser.add_argument("--list-cases", action="store_true")
    args = parser.parse_args()

    config = args.config.resolve()
    source = config.read_text(encoding="utf-8")
    base_python = literal_string(source, "schema_validation.execution.environment.python_base")
    if args.python:
        python = shutil.which(args.python)
        if python is None:
            raise SystemExit(f"Python interpreter not found: {args.python}")
    else:
        python = str(HERE / ".venv-pinned" / "bin" / "python")
        if not Path(python).exists():
            base = shutil.which(base_python)
            if base is None:
                raise SystemExit(f"Python interpreter not found: {base_python}")
            subprocess.run([base, "-m", "venv", str(HERE / ".venv-pinned")], check=True)

    if args.list_cases:
        cases_file = HERE / "cases.json"
        import json
        for item in json.loads(cases_file.read_text(encoding="utf-8")):
            print(item["id"])
        return

    if args.python is None:
        requirements = []
        for name in ("scinumtools3", "jsonschema", "numpy", "matplotlib"):
            requirements.append(name + "==" + literal_string(
                source, f"schema_validation.packages.{name}.version"))
        needs_install = False
        for name in ("scinumtools3", "jsonschema", "numpy", "matplotlib"):
            check = subprocess.run([python, "-c",
                                    "import importlib.metadata as m,sys; "
                                    "print(m.version(sys.argv[1]))", name],
                                   capture_output=True, text=True)
            expected = literal_string(source, f"schema_validation.packages.{name}.version")
            if check.returncode or check.stdout.strip() != expected:
                needs_install = True
        if needs_install:
            subprocess.run([python, "-m", "pip", "install", *requirements], check=True)

    command = [python, str(HERE / "benchmark.py"), "--config", str(config)]
    if args.samples is not None:
        command.extend(("--samples", str(args.samples)))
    for participant in args.participant or ():
        command.extend(("--participant", participant))
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
