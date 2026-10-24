"""Compare uncertainty propagation estimates with analytic and Monte Carlo references."""
import argparse
import fnmatch
import math
from pathlib import Path

import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--figure", type=Path, required=True)
    parser.add_argument("--case", action="append")
    parser.add_argument("--library", action="append")
    parser.add_argument("--samples", type=int)
    args = parser.parse_args()

    from scinumtools3.dip import DIP
    dip = DIP()
    dip.add_file(args.config)
    config = dip.parse()

    def get(path):
        return config[f"uncertainty_propagation.{path}"].value

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd
    import pint
    import metrolopy
    from uncertainties import ufloat
    from scinumtools3.puq import Quantity

    cases = ("linear_conversion", "addition", "product", "reciprocal")
    selected = [case for case in cases if any(
        fnmatch.fnmatchcase(case, pattern)
        for pattern in (args.case or get("workload.selection.cases"))
    )]
    libraries = args.library or get("execution.libraries")
    samples = args.samples or int(get("execution.samples"))
    rng = np.random.default_rng(int(get("execution.seed")))
    registry = pint.UnitRegistry(autoconvert_offset_to_baseunit=True)
    rows = []
    tail = (1 - float(get("semantics.normal_coverage"))) / 2

    def snt(value, sigma, unit):
        return Quantity(value, sigma, unit)

    def evaluate(library, operation):
        result = operation(library)
        if library == "snt":
            return float(result.value()), float(result.uncertainty())
        if library == "pint":
            return float(result.magnitude.nominal_value), float(result.magnitude.std_dev)
        return float(result.x), float(result.u)

    def append(case, library, model, value, sigma, analytic, draws, unit):
        mc_sd = float(np.std(draws, ddof=1))
        low = float(np.quantile(draws, tail))
        high = float(np.quantile(draws, 1-tail))
        rows.append({
            "case_id": case, "library": library, "model": model,
            "nominal": value, "reported_uncertainty": sigma,
            "analytic_standard_deviation": analytic,
            "monte_carlo_mean": float(np.mean(draws)), "monte_carlo_sd": mc_sd,
            "mc_central_low": low, "mc_central_high": high,
            "reported_interval_low": value-sigma,
            "reported_interval_high": value+sigma,
            "mc_coverage": float(np.mean((draws >= value-sigma) & (draws <= value+sigma))),
            "unit": unit,
        })

    for case in selected:
        prefix = f"workload.{case}."
        if case == "linear_conversion":
            x = float(get(prefix+"nominal"))
            sx = float(get(prefix+"standard_deviation"))
            source, target = get(prefix+"source_unit"), get(prefix+"target_unit")
            scale = float(get(prefix+"scale_num")) / float(get(prefix+"scale_den"))
            offset = float(get(prefix+"offset_num")) / float(get(prefix+"offset_den"))
            draws = rng.normal(x, sx, samples)*scale + offset
            analytic = sx*scale
            for library in libraries:
                def operation(which):
                    if which == "snt":
                        source_snt = {"degC": "Cel"}.get(source, source)
                        target_snt = {"degC": "Cel"}.get(target, target)
                        return snt(x, sx, source_snt).convert(target_snt)
                    if which == "pint":
                        return registry.Quantity(ufloat(x, sx), source).to(target)
                    return metrolopy.gummy(x, u=sx, unit=source).convert(target)
                value, sigma = evaluate(library, operation)
                append(case, library, f"{library} standard uncertainty", value, sigma, analytic, draws, target)

        elif case in ("addition", "product"):
            x, sx = float(get(prefix+"x")), float(get(prefix+"sigma_x"))
            y, sy = float(get(prefix+"y")), float(get(prefix+"sigma_y"))
            xx, yy = rng.normal(x, sx, samples), rng.normal(y, sy, samples)
            if case == "addition":
                unit = get(prefix+"unit")
                draws, analytic = xx+yy, math.hypot(sx, sy)
                def operation(which):
                    if which == "snt": return snt(x, sx, unit)+snt(y, sy, unit)
                    if which == "pint": return registry.Quantity(ufloat(x, sx), unit)+registry.Quantity(ufloat(y, sy), unit)
                    return metrolopy.gummy(x, u=sx, unit=unit)+metrolopy.gummy(y, u=sy, unit=unit)
            else:
                xu, yu = get(prefix+"x_unit"), get(prefix+"y_unit")
                unit = f"{xu}*{yu}"
                draws = xx*yy
                analytic = abs(x*y)*math.hypot(sx/x, sy/y)
                def operation(which):
                    if which == "snt": return snt(x, sx, xu)*snt(y, sy, yu)
                    if which == "pint": return registry.Quantity(ufloat(x, sx), xu)*registry.Quantity(ufloat(y, sy), yu)
                    return metrolopy.gummy(x, u=sx, unit=xu)*metrolopy.gummy(y, u=sy, unit=yu)
            for library in libraries:
                value, sigma = evaluate(library, operation)
                model = "SNT absolute bounds" if library == "snt" else f"{library} first-order standard uncertainty"
                append(case, library, model, value, sigma, analytic, draws, unit)

        else:
            x, sx, unit = float(get(prefix+"x")), float(get(prefix+"sigma_x")), get(prefix+"unit")
            draws = 1/rng.normal(x, sx, samples)
            analytic = sx/(x*x)
            def operation(which):
                if which == "snt": return 1/snt(x, sx, unit)
                if which == "pint": return 1/registry.Quantity(ufloat(x, sx), unit)
                return 1/metrolopy.gummy(x, u=sx, unit=unit)
            for library in libraries:
                value, sigma = evaluate(library, operation)
                model = "SNT interval bounds" if library == "snt" else f"{library} first-order standard uncertainty"
                append(case, library, model, value, sigma, analytic, draws, f"1/{unit}")

    frame = pd.DataFrame(rows)
    frame["analytic_vs_mc_relative_error"] = abs(frame.monte_carlo_sd-frame.analytic_standard_deviation)/frame.analytic_standard_deviation
    frame["mc_within_configured_tolerance"] = frame.analytic_vs_mc_relative_error <= float(get("semantics.tolerance_relative"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False)

    fig, ax = plt.subplots(figsize=(10, 5), constrained_layout=True)
    case_order = list(dict.fromkeys(frame.case_id))
    width = 0.8/len(libraries)
    x = np.arange(len(case_order))
    colors = {"snt": "#1878a5", "pint": "#d87524", "metrolopy": "#568a45"}
    for index, library in enumerate(libraries):
        subset = frame[frame.library == library].set_index("case_id").reindex(case_order)
        ratio = subset.reported_uncertainty/subset.monte_carlo_sd
        offset = (index-(len(libraries)-1)/2)*width
        version = get(f"packages.{library}.version")
        ax.bar(x+offset, ratio, width, color=colors.get(library), label=f"{library} {version}")
    ax.axhline(1, color="black", marker="D", markersize=4, linewidth=1, label="Monte Carlo standard deviation")
    names = {"linear_conversion": "temperature conversion", "addition": "addition", "product": "product", "reciprocal": "reciprocal"}
    ax.set_xticks(x, [names[case] for case in case_order])
    ax.set_ylabel("reported uncertainty / Monte Carlo standard deviation")
    ax.set_title(f"Propagation models relative to seeded Monte Carlo · n={samples:,}")
    ax.grid(axis="y", alpha=.25)
    ax.legend(fontsize=8)
    args.figure.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.figure, dpi=int(get("execution.figure_dpi")))
    plt.close(fig)
    print(frame[["case_id", "library", "model", "reported_uncertainty", "analytic_standard_deviation", "monte_carlo_sd"]].to_string(index=False))


if __name__ == "__main__":
    main()
