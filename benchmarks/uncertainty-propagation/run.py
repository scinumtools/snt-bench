"""Run the configured uncertainty propagation comparison."""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))
from result_retention import prune_old_results
from result_metadata import platform_label, sanitize_result_metadata

PACKAGE_DISTS = {
    "snt": "scinumtools3",
    "pint": "Pint",
    "uncertainties": "uncertainties",
    "numpy": "numpy",
    "matplotlib": "matplotlib",
    "metrolopy": "metrolopy",
    "scipy": "scipy",
    "pandas": "pandas",
    "ipython": "ipython",
}


def literal_string(source, wanted):
    parents = []
    for line in source.splitlines():
        match = re.fullmatch(r'( *)([a-z_][a-z0-9_]*)(?: str = (".*"))?', line)
        if not match:
            continue
        indent, name, value = match.groups()
        while parents and parents[-1][0] >= len(indent):
            parents.pop()
        qualified = ".".join([node for _, node in parents] + [name])
        if value is not None and qualified == wanted:
            return ast.literal_eval(value)
        if value is None:
            parents.append((len(indent), name))
    raise ValueError(f"Missing configured string {wanted}")


def executable(value):
    candidate = Path(value)
    if candidate.exists():
        return str(candidate.absolute())
    found = shutil.which(str(value))
    if found:
        return str(Path(found).absolute())
    raise SystemExit(f"Python interpreter not found: {value}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=HERE / "config.dip")
    parser.add_argument("--source", choices=("pinned", "local"), help="SNT3 source to benchmark")
    parser.add_argument("--python", help="Use an existing environment without installing dependencies")
    parser.add_argument("--case", action="append")
    parser.add_argument("--library", action="append", choices=("snt", "pint", "metrolopy"))
    parser.add_argument("--samples", type=int)
    parser.add_argument("--quick", action="store_true", help="Refresh the pinned reference snapshot")
    parser.add_argument("--ready", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    config = args.config.resolve()
    config_text = config.read_text(encoding="utf-8")
    source = args.source or literal_string(config_text, "uncertainty_propagation.execution.target.source")
    if source not in ("pinned", "local"):
        parser.error("source must be pinned or local")

    local_repo = Path(literal_string(config_text, "uncertainty_propagation.execution.paths.local_repo"))
    if not local_repo.is_absolute():
        local_repo = (ROOT / local_repo).resolve()
    env = os.environ.copy()
    if source == "local":
        binding = local_repo / "build" / "python"
        if not list((binding / "scinumtools3").glob("_snt*.*")):
            raise SystemExit(f"Build the local SNT3 Python binding first: {binding}")
        env["PYTHONPATH"] = str(binding)
        env["SNT_BENCH_SOURCE"] = "local"
        local_python = Path(literal_string(config_text, "uncertainty_propagation.execution.paths.local_python_base"))
        base_python = local_python if local_python.is_absolute() else local_repo / local_python
        venv_dir = HERE / ".venv-local"
    else:
        env.pop("PYTHONPATH", None)
        base_python = Path(literal_string(config_text, "uncertainty_propagation.execution.python_base"))
        venv_dir = HERE / ".venv-pinned"

    external_python = args.python is not None
    if external_python:
        python = executable(args.python)
    else:
        python = str(venv_dir / "bin" / "python")
        if not Path(python).exists():
            subprocess.run([executable(base_python), "-m", "venv", str(venv_dir)], check=True)

    if not args.ready:
        if source == "pinned":
            snt_pin = literal_string(config_text, "uncertainty_propagation.packages.snt.version")
            check_snt = subprocess.run(
                [python, "-c", "import importlib.metadata as m; print(m.version('scinumtools3'))"],
                capture_output=True, text=True, env=env,
            )
            if check_snt.returncode or check_snt.stdout.strip() != snt_pin:
                if external_python:
                    raise SystemExit(f"{python} requires scinumtools3=={snt_pin}")
                subprocess.run([python, "-m", "pip", "install", f"scinumtools3=={snt_pin}"], check=True)
        os.execve(python, [python, __file__, *sys.argv[1:], "--ready"], env)

    from scinumtools3.dip import DIP
    import scinumtools3

    dip = DIP()
    dip.add_file(config)
    values = dip.parse()

    def get(path):
        return values[f"uncertainty_propagation.{path}"].value

    package_names = tuple(PACKAGE_DISTS)
    required_names = package_names if source == "pinned" else package_names[1:]
    expected = {name: get(f"packages.{name}.version") for name in required_names}
    installed = subprocess.run(
        [python, "-c", "import importlib.metadata as m,sys; print(' '.join(m.version(n) for n in sys.argv[1:]))",
         *(PACKAGE_DISTS[name] for name in required_names)],
        capture_output=True, text=True, env=env,
    )
    found = installed.stdout.strip().split() if installed.returncode == 0 else []
    requirements = [f"{PACKAGE_DISTS[name]}=={expected[name]}" for name in required_names]
    wanted = [expected[name] for name in required_names]
    if found != wanted:
        if external_python:
            raise SystemExit(f"{python} requires: {' '.join(requirements)}")
        if env.get("SNT_BENCH_DEPS_INSTALLED") == "1":
            raise SystemExit(f"Package versions still differ after installation: {' '.join(requirements)}")
        subprocess.run([python, "-m", "pip", "install", *requirements], check=True, env=env)
        env["SNT_BENCH_DEPS_INSTALLED"] = "1"
        os.execve(python, [python, __file__, *sys.argv[1:]], env)

    output_dir = Path(get("execution.output_dir"))
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = output_dir / f"uncertainty_{source}_{stamp}"
    command = [python, str(HERE / "benchmark.py"), "--config", str(config),
               "--output", str(base.with_suffix(".csv")), "--figure", str(base.with_suffix(".png"))]
    for case in args.case or ():
        command.extend(("--case", case))
    for library in args.library or ():
        command.extend(("--library", library))
    if args.samples is not None:
        command.extend(("--samples", str(args.samples)))
    subprocess.run(command, check=True, env=env)

    projects = {
        name: {"version": get(f"packages.{name}.version"),
               "website": get(f"packages.{name}.website"),
               "release": get(f"packages.{name}.release")}
        for name in package_names
    }
    if source == "local":
        projects["snt"]["configured_pin"] = projects["snt"]["version"]
        projects["snt"]["version"] = f"{scinumtools3.__version__} (local checkout)"

    provenance = {
        name: get(f"provenance.{name}")
        for name in ("gum", "gum_amendment_2026", "monte_carlo", "pint_uncertainties", "uncertainty_model", "metrolopy")
    }
    settings = {
        "source": source,
        "samples": args.samples if args.samples is not None else get("execution.samples"),
        "seed": get("execution.seed"),
        "cases": args.case if args.case is not None else get("workload.selection.cases"),
        "libraries": args.library if args.library is not None else get("execution.libraries"),
        "coverage": get("semantics.normal_coverage"),
        "one_sigma_normal_coverage": get("semantics.one_sigma_normal_coverage"),
        "tolerance_relative": get("semantics.tolerance_relative"),
    }
    revision = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip() or None
    pyver = subprocess.run([python, "-c", "import sys; print(sys.version.split()[0])"],
                           capture_output=True, text=True, check=True, env=env).stdout.strip()
    source_hashes = {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                     for name in ("run.py", "benchmark.py")}
    local_revision = None
    local_status = []
    local_diff_hash = None
    if source == "local":
        local_revision = subprocess.run(["git", "-C", str(local_repo), "rev-parse", "HEAD"],
                                        capture_output=True, text=True).stdout.strip() or None
        local_status = subprocess.run(["git", "-C", str(local_repo), "status", "--short"],
                                      capture_output=True, text=True).stdout.splitlines()
        local_diff = subprocess.run(["git", "-C", str(local_repo), "diff", "HEAD", "--binary"],
                                    capture_output=True).stdout
        local_diff_hash = hashlib.sha256(local_diff).hexdigest()
    snapshot = {
        "config_path": "benchmarks/uncertainty-propagation/config.dip",
        "config_sha256": hashlib.sha256(config_text.encode()).hexdigest(),
        "config_source": config_text,
        "platform": platform_label(),
        "python": pyver,
        "repository_revision": revision,
        "benchmark_source_sha256": source_hashes,
        "packages": projects,
        "provenance": provenance,
        "effective_settings": settings,
        "snt_local_revision": local_revision,
        "snt_local_worktree_status": local_status,
        "snt_local_diff_sha256": local_diff_hash,
        "command": ["python", "benchmark.py", "--config", "config.dip"],
    }
    base.with_suffix(".config.json").write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    if args.quick and source == "pinned":
        for suffix in (".csv", ".png", ".config.json"):
            (output_dir / ("reference-quick" + suffix)).write_bytes(base.with_suffix(suffix).read_bytes())
    sanitize_result_metadata(output_dir, ROOT)
    removed = prune_old_results(output_dir)
    if removed:
        print(f"Pruned {len(removed)} files from result groups older than the newest ten.")


if __name__ == "__main__":
    main()
