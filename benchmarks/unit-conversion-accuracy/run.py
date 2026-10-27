"""Install configured dependencies and execute the conversion accuracy suite."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import ast
import re
import shutil
import subprocess as sp
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))
from result_metadata import platform_label, sanitize_result_metadata
from result_retention import prune_old_results

def literal_string(source, wanted):
    parents=[]
    for line in source.splitlines():
        match=re.fullmatch(r'( *)([a-z_][a-z0-9_]*)(?: str = (".*"))?',line)
        if not match: continue
        indent,name,value=match.groups()
        while parents and parents[-1][0]>=len(indent): parents.pop()
        qualified=".".join([node for _,node in parents]+[name])
        if value is not None and qualified==wanted: return ast.literal_eval(value)
        if value is None: parents.append((len(indent),name))
    raise ValueError(f"Missing configured string {wanted}")

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, default=HERE / "config.dip")
    p.add_argument("--python", help="Use an existing Python environment (skip environment bootstrap).")
    p.add_argument("--case", action="append", help="Case ID glob; may be repeated.")
    p.add_argument("--library", action="append", choices=("snt", "pint", "unyt", "astropy"))
    p.add_argument("--quick", action="store_true", help="Also update the tracked reference snapshot.")
    a = p.parse_args()
    config = a.config.resolve(); text = config.read_text(encoding="utf-8")
    snt_version=literal_string(text,"unit_conversion_accuracy.packages.snt.version")
    python = a.python or str(HERE / ".venv-pinned" / "bin" / "python")
    if not a.python and not Path(python).exists():
        base_python=literal_string(text,"unit_conversion_accuracy.execution.python_base")
        subprocess.run([shutil.which(base_python) or base_python, "-m", "venv", str(HERE / ".venv-pinned")], check=True)
    probe = subprocess.run([python, "-c", "import importlib.metadata as m; print(m.version('scinumtools3'))"], text=True, capture_output=True)
    if probe.returncode or probe.stdout.strip() != snt_version:
        if a.python: raise SystemExit(f"Environment must contain scinumtools3=={snt_version}: {probe.stderr}")
        subprocess.run([python, "-m", "pip", "install", f"scinumtools3=={snt_version}"], check=True)
        subprocess.run([python, __file__, *sys.argv[1:]], check=True); return
    # Install exactly the package pins declared in the source-of-truth configuration.
    check = "import importlib.metadata as m,sys; print(' '.join(f'{n}=={m.version(n)}' for n in sys.argv[1:]))"
    names = ["Pint", "unyt", "astropy", "numpy", "matplotlib"]
    versions = subprocess.run([python, "-c", "from scinumtools3.dip import DIP; import sys; d=DIP(); d.add_file(sys.argv[1]); v=d.parse(); print(' '.join(''.join([n, '==', v[f'unit_conversion_accuracy.packages.{k}.version'].value]) for k,n in [('pint','Pint'),('unyt','unyt'),('astropy','astropy'),('numpy','numpy'),('matplotlib','matplotlib')]))", str(config)], text=True, capture_output=True, check=True).stdout.strip().split()
    installed = subprocess.run([python, "-c", check, *names], text=True, capture_output=True)
    if installed.returncode or installed.stdout.strip().split() != versions:
        if a.python: raise SystemExit(f"Pinned requirements differ; expected {versions}, found {installed.stdout}")
        subprocess.run([python, "-m", "pip", "install", *versions], check=True)
        subprocess.run([python, __file__, *sys.argv[1:]], check=True); return
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    config_probe="from scinumtools3.dip import DIP; import sys; d=DIP(); d.add_file(sys.argv[1]); v=d.parse(); print(v['unit_conversion_accuracy.execution.output_dir'].value)"
    output_dir=subprocess.run([python,"-c",config_probe,str(config)],text=True,capture_output=True,check=True).stdout.strip()
    out=Path(output_dir); out=out if out.is_absolute() else ROOT/out; out.mkdir(parents=True,exist_ok=True)
    base = out / f"conversion_accuracy_{stamp}"
    command = [python, str(HERE / "benchmark.py"), "--config", str(config), "--output", str(base.with_suffix('.csv')), "--figure", str(base.with_suffix('.png'))]
    for x in a.case or (): command.extend(["--case", x])
    for x in a.library or (): command.extend(["--library", x])
    subprocess.run(command, check=True)
    metadata_code="from scinumtools3.dip import DIP; import sys,json; d=DIP(); d.add_file(sys.argv[1]); v=d.parse(); p='unit_conversion_accuracy.packages.'; print(json.dumps({n:{'version':v[p+n+'.version'].value,'website':v[p+n+'.website'].value,'release':v[p+n+'.release'].value} for n in ('snt','pint','unyt','astropy','numpy','matplotlib')}))"
    projects=json.loads(subprocess.run([python,"-c",metadata_code,str(config)],text=True,capture_output=True,check=True).stdout)
    provenance_code="from scinumtools3.dip import DIP; import sys,json; d=DIP(); d.add_file(sys.argv[1]); v=d.parse(); p='unit_conversion_accuracy.provenance.'; keys=('si_brochure','error_metrics','foot_definition','rational_arithmetic'); print(json.dumps({k:v[p+k].value for k in keys}))"
    provenance=json.loads(subprocess.run([python,"-c",provenance_code,str(config)],text=True,capture_output=True,check=True).stdout)
    revision=sp.run(["git","-C",str(ROOT),"rev-parse","HEAD"],capture_output=True,text=True).stdout.strip() or None
    pyver=subprocess.run([python,"-c","import sys; print(sys.version.split()[0])"],capture_output=True,text=True,check=True).stdout.strip()
    source_hashes={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in ("run.py","benchmark.py")}
    snapshot = {"config_path": "benchmarks/unit-conversion-accuracy/config.dip", "config_sha256": hashlib.sha256(text.encode()).hexdigest(), "config_source": text, "platform": platform_label(), "python": pyver, "repository_revision": revision, "benchmark_source_sha256": source_hashes, "packages": projects, "provenance": provenance, "selected_cases": a.case, "selected_libraries": a.library, "command": ["python", "benchmark.py", "--config", "config.dip"]}
    base.with_suffix('.config.json').write_text(json.dumps(snapshot, indent=2)+"\n", encoding="utf-8")
    if a.quick:
        for ext in (".csv", ".png", ".config.json"):
            (out / ("reference-quick"+ext)).write_bytes(base.with_suffix(ext).read_bytes())
    sanitize_result_metadata(out, ROOT, (base.name, "reference-quick") if a.quick else (base.name,))
    prune_old_results(out)

if __name__ == "__main__": main()
