"""Compare propagated uncertainty estimates with analytic and Monte Carlo references."""
import argparse, fnmatch, math
from pathlib import Path
import numpy as np

def main():
 p=argparse.ArgumentParser(description=__doc__); p.add_argument("--config",type=Path,required=True); p.add_argument("--output",type=Path,required=True); p.add_argument("--figure",type=Path,required=True); p.add_argument("--case",action="append"); p.add_argument("--library",action="append"); p.add_argument("--samples",type=int)
 a=p.parse_args()
 from scinumtools3.dip import DIP
 d=DIP(); d.add_file(a.config); cfg=d.parse()
 def get(path):return cfg[f"uncertainty_propagation.{path}"].value
 import pandas as pd, matplotlib
 matplotlib.use("Agg")
 import matplotlib.pyplot as plt, pint
 from uncertainties import ufloat
 from scinumtools3.puq import Quantity
 cases={"linear_conversion":("linear_conversion",),"addition":("addition",),"product":("product",),"reciprocal":("reciprocal",)}
 selected=[k for k in cases if any(fnmatch.fnmatchcase(k,x) for x in (a.case or get("workload.selection.cases")))]; libs=a.library or get("execution.libraries"); n=a.samples or int(get("execution.samples")); rng=np.random.default_rng(int(get("execution.seed"))); ur=pint.UnitRegistry(autoconvert_offset_to_baseunit=True); rows=[]
 tail=(1-float(get("semantics.normal_coverage")))/2
 def snt(x,sigma,unit):return Quantity(x,sigma,unit)
 for case in selected:
  spec=case; pfx="workload."+spec+"."; mc=rng
  if case=="linear_conversion":
   x=float(get(pfx+"nominal")); sx=float(get(pfx+"standard_deviation")); vals=mc.normal(x,sx,n)
   source=get(pfx+"source_unit"); target=get(pfx+"target_unit")
   scale=float(get(pfx+"scale_num"))/float(get(pfx+"scale_den")); offset=float(get(pfx+"offset_num"))/float(get(pfx+"offset_den"))
   out=vals*scale+offset
   nominal=x*scale+offset; analytic=sx*scale
   for lib in libs:
    if lib=="snt": q=snt(x,sx,{"degC":"Cel"}.get(source,source)).convert({"degC":"Cel"}.get(target,target)); y=float(q.value()); sigma=float(q.uncertainty())
    else:
     q=ur.Quantity(ufloat(x,sx),"degC").to("degF"); y=float(q.magnitude.nominal_value); sigma=float(q.magnitude.std_dev)
    rows.append(dict(case_id=case,library=lib,model="SNT uncertainty magnitude" if lib=="snt" else "Pint standard deviation",nominal=y,reported_uncertainty=sigma,analytic_standard_deviation=analytic,monte_carlo_mean=float(np.mean(out)),monte_carlo_sd=float(np.std(out,ddof=1)),mc_central_low=float(np.quantile(out,tail)),mc_central_high=float(np.quantile(out,1-tail)),reported_interval_low=y-sigma,reported_interval_high=y+sigma,mc_coverage=float(np.mean((out>=y-sigma)&(out<=y+sigma))),unit="degF"))
  elif case=="addition":
   x=float(get(pfx+"x")); sx=float(get(pfx+"sigma_x")); y=float(get(pfx+"y")); sy=float(get(pfx+"sigma_y")); unit=get(pfx+"unit"); xx=mc.normal(x,sx,n); yy=mc.normal(y,sy,n); out=xx+yy; nom=x+y; analytic=math.hypot(sx,sy)
   for lib in libs:
    if lib=="snt": q=snt(x,sx,unit)+snt(y,sy,unit); v=float(q.value()); sigma=float(q.uncertainty())
    else: q=ur.Quantity(ufloat(x,sx),unit)+ur.Quantity(ufloat(y,sy),unit); v=float(q.magnitude.nominal_value); sigma=float(q.magnitude.std_dev)
    rows.append(dict(case_id=case,library=lib,model="SNT absolute bound" if lib=="snt" else "GUM first-order standard deviation",nominal=v,reported_uncertainty=sigma,analytic_standard_deviation=analytic,monte_carlo_mean=float(np.mean(out)),monte_carlo_sd=float(np.std(out,ddof=1)),mc_central_low=float(np.quantile(out,tail)),mc_central_high=float(np.quantile(out,1-tail)),reported_interval_low=v-sigma,reported_interval_high=v+sigma,mc_coverage=float(np.mean((out>=v-sigma)&(out<=v+sigma))),unit=unit))
  elif case=="product":
   x=float(get(pfx+"x")); sx=float(get(pfx+"sigma_x")); y=float(get(pfx+"y")); sy=float(get(pfx+"sigma_y")); xu=get(pfx+"x_unit"); yu=get(pfx+"y_unit"); xx=mc.normal(x,sx,n); yy=mc.normal(y,sy,n); out=xx*yy; nom=x*y; analytic=abs(nom)*math.hypot(sx/x,sy/y)
   for lib in libs:
    if lib=="snt": q=snt(x,sx,xu)*snt(y,sy,yu); v=float(q.value()); sigma=float(q.uncertainty())
    else: q=ur.Quantity(ufloat(x,sx),xu)*ur.Quantity(ufloat(y,sy),yu); v=float(q.magnitude.nominal_value); sigma=float(q.magnitude.std_dev)
    rows.append(dict(case_id=case,library=lib,model="SNT interval bound" if lib=="snt" else "GUM first-order standard deviation",nominal=v,reported_uncertainty=sigma,analytic_standard_deviation=analytic,monte_carlo_mean=float(np.mean(out)),monte_carlo_sd=float(np.std(out,ddof=1)),mc_central_low=float(np.quantile(out,tail)),mc_central_high=float(np.quantile(out,1-tail)),reported_interval_low=v-sigma,reported_interval_high=v+sigma,mc_coverage=float(np.mean((out>=v-sigma)&(out<=v+sigma))),unit=f"{xu}*{yu}"))
  else:
   x=float(get(pfx+"x")); sx=float(get(pfx+"sigma_x")); unit=get(pfx+"unit"); xx=mc.normal(x,sx,n); out=1/xx; nom=1/x; analytic=sx/(x*x)
   for lib in libs:
    if lib=="snt": q=1/snt(x,sx,unit); v=float(q.value()); sigma=float(q.uncertainty())
    else: q=1/ur.Quantity(ufloat(x,sx),unit); v=float(q.magnitude.nominal_value); sigma=float(q.magnitude.std_dev)
    rows.append(dict(case_id=case,library=lib,model="SNT interval bound" if lib=="snt" else "GUM first-order standard deviation",nominal=v,reported_uncertainty=sigma,analytic_standard_deviation=analytic,monte_carlo_mean=float(np.mean(out)),monte_carlo_sd=float(np.std(out,ddof=1)),mc_central_low=float(np.quantile(out,tail)),mc_central_high=float(np.quantile(out,1-tail)),reported_interval_low=v-sigma,reported_interval_high=v+sigma,mc_coverage=float(np.mean((out>=v-sigma)&(out<=v+sigma))),unit=f"1/{unit}"))
 df=pd.DataFrame(rows); df["analytic_vs_mc_relative_error"]=abs(df.monte_carlo_sd-df.analytic_standard_deviation)/df.analytic_standard_deviation
 df["mc_within_configured_tolerance"]=df.analytic_vs_mc_relative_error<=float(get("semantics.tolerance_relative"))
 a.output.parent.mkdir(parents=True,exist_ok=True); df.to_csv(a.output,index=False)
 fig,ax=plt.subplots(figsize=(10,5),constrained_layout=True)
 cases_order=list(dict.fromkeys(df.case_id)); width=.34; x=np.arange(len(cases_order))
 for offset,lib,color in ((-width/2,"snt","#1878a5"),(width/2,"pint","#d87524")):
  subset=df[df.library==lib].set_index("case_id").reindex(cases_order)
  ratio=subset.reported_uncertainty/subset.monte_carlo_sd
  ax.bar(x+offset,ratio,width,color=color,label=f"{lib} {get('packages.'+lib+'.version')}")
 ax.axhline(1,color="black",marker="D",markersize=4,linewidth=1,label="Monte Carlo standard deviation")
 ax.set_xticks(x,[{"linear_conversion":"temperature conversion","addition":"addition","product":"product","reciprocal":"reciprocal"}[case] for case in cases_order]); ax.set_ylabel("reported uncertainty / Monte Carlo standard deviation"); ax.set_title(f"Propagation models relative to seeded Monte Carlo · n={n:,}"); ax.grid(axis="y",alpha=.25); ax.legend(fontsize=8)
 a.figure.parent.mkdir(parents=True,exist_ok=True); fig.savefig(a.figure,dpi=int(get("execution.figure_dpi"))); plt.close(fig)
 print(df[["case_id","library","model","reported_uncertainty","analytic_standard_deviation","monte_carlo_sd"]].to_string(index=False))
if __name__=="__main__":main()
