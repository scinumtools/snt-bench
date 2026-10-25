"""Compare propagated uncertainties with analytic and Monte Carlo references."""
import argparse
import fnmatch
import math
import os
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
    from uncertainties import correlated_values_norm, ufloat
    import scinumtools3
    from scinumtools3.puq import Quantity

    cases = (
        "linear_conversion", "addition", "product", "reciprocal",
        "square_nonlinear", "correlated_addition", "rectangular_linear",
    )
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
    one_sigma_coverage = float(get("semantics.one_sigma_normal_coverage"))
    local_snt = os.environ.get("SNT_BENCH_SOURCE") == "local"

    def snt(value, sigma, unit):
        return Quantity(value, sigma, unit)

    def evaluate(library, operation):
        result = operation(library)
        if library == "snt":
            return float(result.value()), float(result.uncertainty())
        if library == "pint":
            return float(result.magnitude.nominal_value), float(result.magnitude.std_dev)
        return float(result.x), float(result.u)

    def append(case, library, model, value, sigma, reference_sd, draws, unit, status="ok"):
        mc_sd = float(np.std(draws, ddof=1))
        mc_mean = float(np.mean(draws))
        low = float(np.quantile(draws, tail))
        high = float(np.quantile(draws, 1-tail))
        coverage = float(np.mean((draws >= value-sigma) & (draws <= value+sigma)))
        rows.append({
            "case_id": case, "library": library, "status": status, "model": model,
            "sample_count": len(draws),
            "nominal": value, "reported_uncertainty": sigma,
            "reference_standard_deviation": reference_sd,
            "monte_carlo_mean": mc_mean, "monte_carlo_sd": mc_sd,
            "mc_central_low": low, "mc_central_high": high,
            "reported_interval_low": value-sigma,
            "reported_interval_high": value+sigma,
            "mc_coverage": coverage,
            "coverage_minus_normal_one_sigma": coverage-one_sigma_coverage,
            "nominal_minus_mc_mean": value-mc_mean,
            "nominal_relative_bias": (value-mc_mean)/max(abs(mc_mean), 1e-15),
            "reported_uncertainty_minus_mc_sd": sigma-mc_sd,
            "reported_uncertainty_relative_error": (sigma-mc_sd)/mc_sd if mc_sd else math.nan,
            "reference_sd_relative_error": (sigma-reference_sd)/reference_sd if reference_sd else math.nan,
            "unit": unit,
        })

    def unsupported(case, library, draws, unit, reason):
        rows.append({
            "case_id": case, "library": library, "status": "unsupported", "model": reason,
            "sample_count": len(draws), "nominal": math.nan,
            "reported_uncertainty": math.nan, "reference_standard_deviation": math.nan,
            "monte_carlo_mean": float(np.mean(draws)), "monte_carlo_sd": float(np.std(draws, ddof=1)),
            "mc_central_low": float(np.quantile(draws, tail)),
            "mc_central_high": float(np.quantile(draws, 1-tail)),
            "reported_interval_low": math.nan, "reported_interval_high": math.nan,
            "mc_coverage": math.nan, "coverage_minus_normal_one_sigma": math.nan,
            "nominal_minus_mc_mean": math.nan, "nominal_relative_bias": math.nan,
            "reported_uncertainty_minus_mc_sd": math.nan,
            "reported_uncertainty_relative_error": math.nan,
            "reference_sd_relative_error": math.nan, "unit": unit,
        })

    def wilson_interval(coverage, count, z=1.959963984540054):
        if not math.isfinite(coverage) or not count:
            return math.nan, math.nan
        denominator = 1 + z*z/count
        center = (coverage + z*z/(2*count)) / denominator
        half = z*math.sqrt(coverage*(1-coverage)/count + z*z/(4*count*count)) / denominator
        return center-half, center+half

    for case in selected:
        prefix = f"workload.{case}."
        if case == "linear_conversion":
            x, sx = float(get(prefix+"nominal")), float(get(prefix+"standard_deviation"))
            source, target = get(prefix+"source_unit"), get(prefix+"target_unit")
            scale = float(get(prefix+"scale_num")) / float(get(prefix+"scale_den"))
            offset = float(get(prefix+"offset_num")) / float(get(prefix+"offset_den"))
            draws = rng.normal(x, sx, samples)*scale + offset
            reference_sd = sx*scale
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
                append(case, library, f"{library} standard uncertainty", value, sigma, reference_sd, draws, target)

        elif case in ("addition", "product"):
            x, sx = float(get(prefix+"x")), float(get(prefix+"sigma_x"))
            y, sy = float(get(prefix+"y")), float(get(prefix+"sigma_y"))
            xx, yy = rng.normal(x, sx, samples), rng.normal(y, sy, samples)
            if case == "addition":
                unit = get(prefix+"unit")
                draws, reference_sd = xx+yy, math.hypot(sx, sy)
                def operation(which):
                    if which == "snt": return snt(x, sx, unit)+snt(y, sy, unit)
                    if which == "pint": return registry.Quantity(ufloat(x, sx), unit)+registry.Quantity(ufloat(y, sy), unit)
                    return metrolopy.gummy(x, u=sx, unit=unit)+metrolopy.gummy(y, u=sy, unit=unit)
            else:
                xu, yu = get(prefix+"x_unit"), get(prefix+"y_unit")
                unit = f"{xu}*{yu}"
                draws = xx*yy
                reference_sd = math.sqrt((y*sx)**2 + (x*sy)**2 + (sx*sy)**2)
                def operation(which):
                    if which == "snt": return snt(x, sx, xu)*snt(y, sy, yu)
                    if which == "pint": return registry.Quantity(ufloat(x, sx), xu)*registry.Quantity(ufloat(y, sy), yu)
                    return metrolopy.gummy(x, u=sx, unit=xu)*metrolopy.gummy(y, u=sy, unit=yu)
            for library in libraries:
                value, sigma = evaluate(library, operation)
                model = "PUQ interval bound" if library == "snt" else f"{library} first-order standard uncertainty"
                append(case, library, model, value, sigma, reference_sd, draws, unit)

        elif case == "reciprocal":
            x, sx, unit = float(get(prefix+"x")), float(get(prefix+"sigma_x")), get(prefix+"unit")
            draws = 1/rng.normal(x, sx, samples)
            reference_sd = sx/(x*x)
            def operation(which):
                if which == "snt": return 1/snt(x, sx, unit)
                if which == "pint": return 1/registry.Quantity(ufloat(x, sx), unit)
                return 1/metrolopy.gummy(x, u=sx, unit=unit)
            for library in libraries:
                value, sigma = evaluate(library, operation)
                model = "PUQ interval bound" if library == "snt" else f"{library} first-order standard uncertainty"
                append(case, library, model, value, sigma, reference_sd, draws, f"1/{unit}")

        elif case == "square_nonlinear":
            x, sx, unit = float(get(prefix+"x")), float(get(prefix+"sigma_x")), get(prefix+"unit")
            draws = rng.normal(x, sx, samples)**2
            reference_sd = math.sqrt(2*sx**4 + 4*x*x*sx*sx)
            out_unit = f"{unit}**2"
            def operation(which):
                if which == "snt":
                    q = snt(x, sx, unit)
                    return q*q
                if which == "pint":
                    q = registry.Quantity(ufloat(x, sx), unit)
                    return q*q
                q = metrolopy.gummy(x, u=sx, unit=unit)
                return q*q
            for library in libraries:
                value, sigma = evaluate(library, operation)
                model = f"{library} first-order uncertainty" if library != "snt" else "PUQ first-order uncertainty"
                append(case, library, model, value, sigma, reference_sd, draws, out_unit)

        elif case == "correlated_addition":
            x, sx = float(get(prefix+"x")), float(get(prefix+"sigma_x"))
            y, sy = float(get(prefix+"y")), float(get(prefix+"sigma_y"))
            rho, unit = float(get(prefix+"correlation")), get(prefix+"unit")
            covariance = rho*sx*sy
            draws = rng.multivariate_normal([x, y], [[sx*sx, covariance], [covariance, sy*sy]], samples).sum(axis=1)
            reference_sd = math.sqrt(sx*sx+sy*sy+2*covariance)
            for library in libraries:
                if library == "snt" and not hasattr(Quantity, "correlate"):
                    unsupported(case, library, draws, unit, "Pinned SNT3 release does not expose correlated inputs")
                    continue
                def operation(which):
                    if which == "snt":
                        qx, qy = snt(x, sx, unit), snt(y, sy, unit)
                        Quantity.correlate(qx, qy, rho)
                        return qx+qy
                    if which == "pint":
                        ux, uy = correlated_values_norm([(x, sx), (y, sy)], [[1, rho], [rho, 1]])
                        return registry.Quantity(ux, unit)+registry.Quantity(uy, unit)
                    gx, gy = metrolopy.gummy.create(
                        [x, y], u=[sx, sy], correlation_matrix=[[1, rho], [rho, 1]], unit=unit
                    )
                    return gx+gy
                value, sigma = evaluate(library, operation)
                append(case, library, f"{library} correlated standard uncertainty", value, sigma, reference_sd, draws, unit)

        elif case == "rectangular_linear":
            x = float(get(prefix+"x"))
            sx, unit = float(get(prefix+"standard_deviation")), get(prefix+"unit")
            half_width = math.sqrt(3)*sx
            draws = rng.uniform(x-half_width, x+half_width, samples)
            reference_sd = sx
            for library in libraries:
                def operation(which):
                    if which == "snt": return snt(x, sx, unit)
                    if which == "pint": return registry.Quantity(ufloat(x, sx), unit)
                    return metrolopy.gummy(x, u=sx, unit=unit)
                value, sigma = evaluate(library, operation)
                model = f"{library} first-order from standard deviation"
                append(case, library, model, value, sigma, reference_sd, draws, unit)

    frame = pd.DataFrame(rows)
    frame["mc_reference_relative_error"] = abs(frame.monte_carlo_sd-frame.reference_standard_deviation)/frame.reference_standard_deviation
    frame["mc_within_configured_tolerance"] = (
        frame.mc_reference_relative_error <= float(get("semantics.tolerance_relative"))
    ).astype("boolean")
    frame.loc[frame.status != "ok", "mc_within_configured_tolerance"] = pd.NA
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output, index=False)

    valid = frame[frame.status == "ok"]
    case_order = list(dict.fromkeys(case for case in selected if case in set(valid.case_id)))
    width = 0.8/max(1, len(libraries))
    x = np.arange(len(case_order))
    colors = {"snt": "#1878a5", "pint": "#d87524", "metrolopy": "#568a45"}
    fig, (ax, coverage_ax) = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    for index, library in enumerate(libraries):
        subset = valid[valid.library == library].set_index("case_id").reindex(case_order)
        offset = (index-(len(libraries)-1)/2)*width
        version = get(f"packages.{library}.version")
        if library == "snt" and local_snt:
            version = f"{scinumtools3.__version__} local"
        ax.bar(x+offset, subset.reported_uncertainty/subset.monte_carlo_sd, width,
               color=colors.get(library), label=f"{library} {version}")
    ax.axhline(1, color="black", linewidth=1, label="Monte Carlo standard deviation")
    ax.set_ylabel("reported uncertainty / Monte Carlo SD")
    ax.set_title(f"Uncertainty spread relative to seeded Monte Carlo · n={samples:,}")
    ax.grid(axis="y", alpha=.25)
    coverage_ax.axhline(one_sigma_coverage*100, color="black", linestyle="--", linewidth=1,
                        label="Normal ±1σ reference (68.27%)")
    coverage_ax.set_ylabel("interval coverage (%)")
    case_labels = {
        "linear_conversion": "temperature conversion", "addition": "addition",
        "product": "product", "reciprocal": "reciprocal",
        "square_nonlinear": "square (nonlinear)",
        "correlated_addition": "correlated addition",
        "rectangular_linear": "uniform input",
    }
    coverage_ax.set_xticks(x, [case_labels[case] for case in case_order], rotation=12, ha="right")
    coverage_ax.grid(axis="y", alpha=.25)
    for index, library in enumerate(libraries):
        subset = valid[valid.library == library].set_index("case_id").reindex(case_order)
        offset = (index-(len(libraries)-1)/2)*width
        intervals = [wilson_interval(value, int(count)) if pd.notna(value) and pd.notna(count)
                     else (math.nan, math.nan)
                     for value, count in zip(subset.mc_coverage, subset.sample_count)]
        lower = np.array([pair[0] for pair in intervals])
        upper = np.array([pair[1] for pair in intervals])
        coverage = subset.mc_coverage.to_numpy(dtype=float)
        coverage_ax.errorbar(
            x+offset, coverage*100,
            yerr=np.vstack(((coverage-lower)*100, (upper-coverage)*100)),
            fmt="o", markersize=4, capsize=4, elinewidth=1, linestyle="none", color=colors.get(library),
        )
    coverage_bounds = [wilson_interval(row.mc_coverage, int(row.sample_count))
                       for row in valid.itertuples() if pd.notna(row.mc_coverage)]
    if coverage_bounds:
        lower_bound = min(pair[0] for pair in coverage_bounds)
        upper_bound = max(pair[1] for pair in coverage_bounds)
        coverage_ax.set_ylim(max(0, min(lower_bound, one_sigma_coverage)-0.03)*100,
                             min(1, max(upper_bound, one_sigma_coverage)+0.03)*100)
    handles, labels = ax.get_legend_handles_labels()
    coverage_handles, coverage_labels = coverage_ax.get_legend_handles_labels()
    handles.extend(coverage_handles)
    labels.extend(coverage_labels)
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.98),
               fontsize=8, ncol=len(libraries)+2)
    fig.subplots_adjust(top=0.88, bottom=0.17, hspace=0.12, left=0.12, right=0.98)
    fig.savefig(args.figure, dpi=int(get("execution.figure_dpi")))
    plt.close(fig)
    print(frame[["case_id", "library", "status", "reported_uncertainty", "reference_standard_deviation",
                 "monte_carlo_sd", "mc_coverage", "coverage_minus_normal_one_sigma",
                 "nominal_minus_mc_mean"]].to_string(index=False))


if __name__ == "__main__":
    main()
