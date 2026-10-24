"""Run the configured uncertainty propagation comparison."""
import argparse, ast, hashlib, json, re, shutil, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/"benchmarks"))
from result_retention import prune_old_results
from result_metadata import platform_label, sanitize_result_metadata

def literal_string(source,wanted):
 parents=[]
 for line in source.splitlines():
  match=re.fullmatch(r'( *)([a-z_][a-z0-9_]*)(?: str = (".*"))?',line)
  if not match: continue
  indent,name,value=match.groups()
  while parents and parents[-1][0]>=len(indent): parents.pop()
  qualified=".".join([node for _,node in parents]+[name])
  if value is not None and qualified==wanted:return ast.literal_eval(value)
  if value is None:parents.append((len(indent),name))
 raise ValueError(f"Missing configured string {wanted}")

def main():
 p=argparse.ArgumentParser(description=__doc__); p.add_argument("--config",type=Path,default=HERE/"config.dip"); p.add_argument("--python"); p.add_argument("--case",action="append"); p.add_argument("--library",action="append",choices=("snt","pint","metrolopy")); p.add_argument("--samples",type=int); p.add_argument("--quick",action="store_true"); a=p.parse_args()
 config=a.config.resolve(); text=config.read_text(encoding="utf-8"); python=a.python or str(HERE/".venv-pinned"/"bin"/"python")
 if not a.python and not Path(python).exists():
  base_python=literal_string(text,"uncertainty_propagation.execution.python_base")
  subprocess.run([shutil.which(base_python) or base_python,"-m","venv",str(HERE/".venv-pinned")],check=True)
 names=('snt','pint','uncertainties','numpy','matplotlib','metrolopy','scipy','pandas','ipython')
 code="from scinumtools3.dip import DIP; import sys; d=DIP(); d.add_file(sys.argv[1]); v=d.parse(); print(' '.join(v[f'uncertainty_propagation.packages.{n}.version'].value for n in "+repr(names)+"))"
 expected=subprocess.run([python,"-c",code,str(config)],capture_output=True,text=True)
 if expected.returncode:
  if a.python: raise SystemExit("Selected Python environment must include scinumtools3 and scinumtools3.dip.")
  snt_pin=literal_string(text,"uncertainty_propagation.packages.snt.version")
  subprocess.run([python,"-m","pip","install","scinumtools3=="+snt_pin],check=True); subprocess.run([python,__file__,*sys.argv[1:]],check=True); return
 pins=expected.stdout.strip().split(); req=["scinumtools3=="+pins[0],"Pint=="+pins[1],"uncertainties=="+pins[2],"numpy=="+pins[3],"matplotlib=="+pins[4],"MetroloPy=="+pins[5],"scipy=="+pins[6],"pandas=="+pins[7],"ipython=="+pins[8]]
 dist_names=('scinumtools3','Pint','uncertainties','numpy','matplotlib','metrolopy','scipy','pandas','ipython')
 check=subprocess.run([python,"-c","import importlib.metadata as m; print(' '.join(m.version(n) for n in "+repr(dist_names)+"))"],capture_output=True,text=True)
 if check.returncode or check.stdout.strip().split()!=pins:
  if a.python: raise SystemExit(f"Pinned versions required: {' '.join(req)}")
  subprocess.run([python,"-m","pip","install",*req],check=True); subprocess.run([python,__file__,*sys.argv[1:]],check=True); return
 output_code="from scinumtools3.dip import DIP; import sys; d=DIP(); d.add_file(sys.argv[1]); v=d.parse(); print(v['uncertainty_propagation.execution.output_dir'].value)"
 output_dir=subprocess.run([python,"-c",output_code,str(config)],text=True,capture_output=True,check=True).stdout.strip()
 out=Path(output_dir); out=out if out.is_absolute() else ROOT/out; out.mkdir(parents=True,exist_ok=True); stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"); base=out/f"uncertainty_{stamp}"
 cmd=[python,str(HERE/"benchmark.py"),"--config",str(config),"--output",str(base.with_suffix('.csv')),"--figure",str(base.with_suffix('.png'))]
 for x in a.case or (): cmd.extend(["--case",x])
 for x in a.library or (): cmd.extend(["--library",x])
 if a.samples: cmd.extend(["--samples",str(a.samples)])
 subprocess.run(cmd,check=True)
 meta="from scinumtools3.dip import DIP; import sys,json; d=DIP(); d.add_file(sys.argv[1]); v=d.parse(); p='uncertainty_propagation.packages.'; names="+repr(names)+"; print(json.dumps({n:{'version':v[p+n+'.version'].value,'website':v[p+n+'.website'].value,'release':v[p+n+'.release'].value} for n in names}))"
 projects=json.loads(subprocess.run([python,"-c",meta,str(config)],capture_output=True,text=True,check=True).stdout)
 provenance_code="from scinumtools3.dip import DIP; import sys,json; d=DIP(); d.add_file(sys.argv[1]); v=d.parse(); p='uncertainty_propagation.provenance.'; keys=('gum','gum_amendment_2026','monte_carlo','pint_uncertainties','uncertainty_model','metrolopy'); print(json.dumps({k:v[p+k].value for k in keys}))"
 provenance=json.loads(subprocess.run([python,"-c",provenance_code,str(config)],capture_output=True,text=True,check=True).stdout)
 settings_code="from scinumtools3.dip import DIP; import sys,json; d=DIP(); d.add_file(sys.argv[1]); v=d.parse(); p='uncertainty_propagation.'; g=lambda x:v[p+x].value; print(json.dumps({'samples':g('execution.samples'),'seed':g('execution.seed'),'cases':g('workload.selection.cases'),'libraries':g('execution.libraries'),'coverage':g('semantics.normal_coverage'),'tolerance_relative':g('semantics.tolerance_relative')}))"
 settings=json.loads(subprocess.run([python,"-c",settings_code,str(config)],capture_output=True,text=True,check=True).stdout)
 if a.samples is not None: settings["samples"]=a.samples
 if a.case is not None: settings["cases"]=a.case
 if a.library is not None: settings["libraries"]=a.library
 revision=subprocess.run(["git","-C",str(ROOT),"rev-parse","HEAD"],capture_output=True,text=True).stdout.strip() or None
 pyver=subprocess.run([python,"-c","import sys; print(sys.version.split()[0])"],capture_output=True,text=True,check=True).stdout.strip()
 source_hashes={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in ("run.py","benchmark.py")}
 snap={"config_path":"benchmarks/uncertainty-propagation/config.dip","config_sha256":hashlib.sha256(text.encode()).hexdigest(),"config_source":text,"platform":platform_label(),"python":pyver,"repository_revision":revision,"benchmark_source_sha256":source_hashes,"packages":projects,"provenance":provenance,"effective_settings":settings,"command":["python","benchmark.py","--config","config.dip"]}
 base.with_suffix('.config.json').write_text(json.dumps(snap,indent=2)+"\n",encoding="utf-8")
 if a.quick:
  for ext in (".csv",".png",".config.json"): (out/("reference-quick"+ext)).write_bytes(base.with_suffix(ext).read_bytes())
 sanitize_result_metadata(out,ROOT)
 prune_old_results(out)
if __name__=="__main__":main()
