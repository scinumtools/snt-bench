"""Measure binary64 conversion error against exact rational references."""
import argparse, fnmatch, math, struct
from fractions import Fraction
from pathlib import Path

def ordered_bits(x):
    bits = struct.unpack(">Q", struct.pack(">d", float(x)))[0]
    return (~bits & ((1 << 64)-1)) if bits >> 63 else bits | (1 << 63)

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--config",type=Path,required=True); p.add_argument("--output",type=Path,required=True); p.add_argument("--figure",type=Path,required=True); p.add_argument("--case",action="append"); p.add_argument("--library",action="append")
    a=p.parse_args()
    from scinumtools3.dip import DIP
    d=DIP(); d.add_file(a.config); cfg=d.parse()
    def get(path): return cfg[f"unit_conversion_accuracy.{path}"].value
    import numpy as np, pandas as pd, matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pint, unyt as uy, astropy.units as au
    from scinumtools3.puq import Quantity
    specs={k:{f:get(f"workload.cases.{k}.{f}") for f in fields} for k,fields in {
        "scaled_to_micro":("source_unit","target_unit","scale_num","scale_den"),"foot_to_metre":("source_unit","target_unit","scale_num","scale_den"),"speed_to_kmh":("source_unit","target_unit","scale_num","scale_den"),"celsius_to_kelvin":("source_unit","target_unit","offset_num","offset_den"),"fahrenheit_to_kelvin":("source_unit","target_unit","scale_num","scale_den","offset_num","offset_den")}.items()}
    patterns=a.case or get("execution.cases"); cases=[k for k in specs if any(fnmatch.fnmatchcase(k,x) for x in patterns)]
    libs=a.library or get("execution.libraries")
    if not cases: raise SystemExit("No conversion cases selected")
    ureg=pint.UnitRegistry(autoconvert_offset_to_baseunit=True)
    rows=[]
    def convert(lib,x,spec):
        src,dst=spec["source_unit"],spec["target_unit"]
        if lib=="snt":
            src={"degC":"Cel","ft":"US_ft"}.get(src,src)
            dst={"degC":"Cel","ft":"US_ft"}.get(dst,dst)
            return float(Quantity(x,src).convert(dst).value())
        if lib=="pint": return float(ureg.Quantity(x,src).to(dst).magnitude)
        if lib=="unyt":
            src={"km/h":"km/hr"}.get(src,src); dst={"km/h":"km/hr"}.get(dst,dst)
            return float((x*uy.Unit(src)).to(dst).value)
        src={"degC":"deg_C"}.get(src,src); dst={"degC":"deg_C"}.get(dst,dst)
        units={"ft":au.imperial.ft,"degF":au.imperial.deg_F}
        src_unit=units[src] if src in units else au.Unit(src)
        dst_unit=units[dst] if dst in units else au.Unit(dst)
        q=x*src_unit; out=q.to(dst_unit, equivalencies=au.temperature())
        return float(out.value)
    for cid in cases:
        spec=specs[cid]
        for xin in get("workload.inputs"):
            x=float(xin); xx=Fraction.from_float(x)
            if cid=="celsius_to_kelvin": ref=xx+Fraction(spec["offset_num"],spec["offset_den"])
            elif cid=="fahrenheit_to_kelvin": ref=(xx+Fraction(spec["offset_num"],spec["offset_den"]))*Fraction(spec["scale_num"],spec["scale_den"])
            else: ref=xx*Fraction(spec["scale_num"],spec["scale_den"])
            rounded=float(ref)
            for lib in libs:
                y=convert(lib,x,spec); error=abs(Fraction.from_float(y)-ref); abs_err=float(error); rel=float(error/abs(ref)) if ref else math.nan; ulp=abs(ordered_bits(y)-ordered_bits(rounded))
                atol=Fraction(str(float(get("tolerances.absolute")))); rtol=Fraction(str(float(get("tolerances.relative"))))
                passed=(error<=atol or (bool(ref) and error/abs(ref)<=rtol)) and ulp<=int(get("tolerances.ulp"))
                rows.append({"case_id":cid,"input":x,"source_unit":spec["source_unit"],"target_unit":spec["target_unit"],"library":lib,"output":y,"reference_exact_rational":f"{ref.numerator}/{ref.denominator}","reference_binary64":rounded,"absolute_error":abs_err,"relative_error":rel,"ulp_distance":ulp,"pass":passed})
    df=pd.DataFrame(rows); a.output.parent.mkdir(parents=True,exist_ok=True); df.to_csv(a.output,index=False)
    pivot=df.groupby(["case_id","library"],sort=False).agg(max_ulp=("ulp_distance","max"),max_abs_error=("absolute_error","max"),max_relative_error=("relative_error","max"),all_pass=("pass","all")).reset_index()
    fig,axes=plt.subplots(1,2,figsize=(14,5.4),constrained_layout=True)
    package_versions={lib:get(f"packages.{lib}.version") for lib in libs}
    labels={lib:f"{lib} {package_versions[lib]}" for lib in libs}
    for ax,col,title in [(axes[0],"max_ulp","Maximum ULP distance from rounded exact reference"),(axes[1],"max_relative_error","Maximum relative error")]:
        for lib in libs:
            sub=pivot[pivot.library==lib]; values=sub[col].fillna(0).to_numpy()
            if col=="max_relative_error": values=np.maximum(values,1e-18)
            ax.plot(sub.case_id,values,marker="o",label=labels[lib])
        if col=="max_relative_error": ax.set_yscale("log")
        ax.set_title(title); ax.tick_params(axis="x",rotation=25,labelsize=8); ax.grid(True,which="both",alpha=.25)
    axes[0].set_ylabel("ULP distance (binary64)"); axes[1].set_ylabel("relative error"); axes[1].legend(title="Pinned project",fontsize=8)
    fig.suptitle("Unit conversion accuracy · binary64 outputs"); a.figure.parent.mkdir(parents=True,exist_ok=True); fig.savefig(a.figure,dpi=int(get("execution.figure_dpi"))); plt.close(fig)
    print(pivot.to_string(index=False))
    if not df["pass"].all(): raise SystemExit("At least one conversion result exceeds configured tolerances")
if __name__=="__main__":main()
