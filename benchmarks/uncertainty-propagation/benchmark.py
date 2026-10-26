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
    from scinumtools3.puq import Quantity, sqrt

    cases = (
        "linear_conversion", "addition", "product", "reciprocal", "reciprocal_uniform",
        "square_nonlinear", "sqrt_uniform_boundary", "correlated_addition", "rectangular_linear",
    )
    selected = [case for case in cases if any(
        fnmatch.fnmatchcase(case, pattern)
        for pattern in (args.case or get("workload.selection.cases"))
    )]
    libraries = args.library or get("execution.libraries")
    local_snt_tracks = get("execution.local_snt_tracks")
    if set(local_snt_tracks) - {"fast", "monte_carlo"}:
        raise SystemExit("execution.local_snt_tracks may contain only fast and monte_carlo")
    metrolopy_monte_carlo = bool(get("execution.metrolopy_monte_carlo"))
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

    def append(case, library, model, value, sigma, reference_sd, draws, unit, status="ok",
               interval_bounds=None, coverage_target=None):
        mc_sd = float(np.std(draws, ddof=1))
        mc_mean = float(np.mean(draws))
        low = float(np.quantile(draws, tail))
        high = float(np.quantile(draws, 1-tail))
        interval_low, interval_high = interval_bounds or (value-sigma, value+sigma)
        coverage = float(np.mean((draws >= interval_low) & (draws <= interval_high)))
        target = one_sigma_coverage if coverage_target is None else coverage_target
        rows.append({
            "case_id": case, "library": library, "status": status, "model": model,
            "sample_count": len(draws),
            "nominal": value, "reported_uncertainty": sigma,
            "reference_standard_deviation": reference_sd,
            "monte_carlo_mean": mc_mean, "monte_carlo_sd": mc_sd,
            "mc_central_low": low, "mc_central_high": high,
            "reported_interval_low": interval_low,
            "reported_interval_high": interval_high,
            "mc_coverage": coverage,
            "coverage_target": target,
            "coverage_minus_target": coverage-target,
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
            "mc_coverage": math.nan, "coverage_target": math.nan,
            "coverage_minus_target": math.nan,
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

    def append_snt_monte_carlo(case, inputs, distributions, model, reference_sd, draws, unit):
        result = Quantity.monte_carlo(
            model, inputs, distributions=distributions, samples=samples,
            seed=int(get("execution.seed")), coverage=float(get("semantics.normal_coverage")),
        )
        value = float(result.quantity.value())
        sigma = float(result.quantity.uncertainty())
        append(case, "snt_mc", "SNT3 Monte Carlo", value, sigma, reference_sd,
               draws, unit, interval_bounds=(float(result.lower), float(result.upper)),
               coverage_target=float(get("semantics.normal_coverage")))

    def append_metrolopy_monte_carlo(case, result, reference_sd, draws, unit):
        coverage = float(get("semantics.normal_coverage"))
        metrolopy.Distribution.set_seed(int(get("execution.seed")))
        result.p = coverage
        result.cimethod = "symmetric"
        metrolopy.gummy.simulate([result], n=samples)
        low, high = result.cisim
        append(case, "metrolopy_mc", "MetroloPy Monte Carlo", float(result.xsim),
               float(result.usim), reference_sd, draws, unit,
               interval_bounds=(float(low), float(high)), coverage_target=coverage)

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
                if library == "snt" and local_snt and "fast" not in local_snt_tracks:
                    continue
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
            if local_snt and "snt" in libraries and "monte_carlo" in local_snt_tracks:
                qx = snt(x, sx, {"degC": "Cel"}.get(source, source))
                snt_target = {"degC": "Cel"}.get(target, target)
                append_snt_monte_carlo(case, [qx], ["normal"],
                                       lambda sampled: sampled.convert(snt_target),
                                       reference_sd, draws, target)

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
                if library == "snt" and local_snt and "fast" not in local_snt_tracks:
                    continue
                value, sigma = evaluate(library, operation)
                model = "PUQ fast first-order uncertainty" if library == "snt" else f"{library} first-order standard uncertainty"
                append(case, library, model, value, sigma, reference_sd, draws, unit)
            if local_snt and "snt" in libraries and "monte_carlo" in local_snt_tracks:
                if case == "addition":
                    qx, qy = snt(x, sx, unit), snt(y, sy, unit)
                    mc_model = lambda left, right: left + right
                else:
                    qx, qy = snt(x, sx, xu), snt(y, sy, yu)
                    mc_model = lambda left, right: left * right
                append_snt_monte_carlo(case, [qx, qy], ["normal", "normal"],
                                       mc_model, reference_sd, draws, unit)

        elif case == "reciprocal":
            x, sx, unit = float(get(prefix+"x")), float(get(prefix+"sigma_x")), get(prefix+"unit")
            draws = 1/rng.normal(x, sx, samples)
            reference_sd = sx/(x*x)
            def operation(which):
                if which == "snt": return 1/snt(x, sx, unit)
                if which == "pint": return 1/registry.Quantity(ufloat(x, sx), unit)
                return 1/metrolopy.gummy(x, u=sx, unit=unit)
            for library in libraries:
                if library == "snt" and local_snt and "fast" not in local_snt_tracks:
                    continue
                value, sigma = evaluate(library, operation)
                model = "PUQ fast first-order uncertainty" if library == "snt" else f"{library} first-order standard uncertainty"
                append(case, library, model, value, sigma, reference_sd, draws, f"1/{unit}")
            if local_snt and "snt" in libraries and "monte_carlo" in local_snt_tracks:
                qx = snt(x, sx, unit)
                append_snt_monte_carlo(case, [qx], ["normal"], lambda sampled: 1 / sampled,
                                       reference_sd, draws, f"1/{unit}")

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
                if library == "snt" and local_snt and "fast" not in local_snt_tracks:
                    continue
                value, sigma = evaluate(library, operation)
                model = f"{library} first-order uncertainty" if library != "snt" else "PUQ fast first-order uncertainty"
                append(case, library, model, value, sigma, reference_sd, draws, out_unit)
            if local_snt and "snt" in libraries and "monte_carlo" in local_snt_tracks:
                qx = snt(x, sx, unit)
                append_snt_monte_carlo(case, [qx], ["normal"], lambda sampled: sampled * sampled,
                                       reference_sd, draws, out_unit)

        elif case == "sqrt_uniform_boundary":
            x = float(get(prefix+"x"))
            sx, unit = float(get(prefix+"standard_deviation")), get(prefix+"unit")
            distribution = get(prefix+"input_distribution")
            if distribution != "uniform":
                raise ValueError(f"{case}.input_distribution must be uniform")
            half_width = math.sqrt(3)*sx
            lower_input, upper_input = x-half_width, x+half_width
            if lower_input < 0:
                raise ValueError(f"{case} square-root input support must be nonnegative")
            input_draws = rng.uniform(lower_input, upper_input, samples)
            draws = np.sqrt(input_draws)
            output_mean = (2/3)*(upper_input**1.5-lower_input**1.5)/(upper_input-lower_input)
            reference_sd = math.sqrt((lower_input+upper_input)/2-output_mean*output_mean)
            out_unit = "m"
            snt_input_unit = unit.replace("**", "")
            def operation(which):
                if which == "snt": return sqrt(snt(x, sx, snt_input_unit))
                if which == "pint": return registry.Quantity(ufloat(x, sx), unit)**0.5
                return metrolopy.gummy(x, u=sx, unit=unit)**0.5
            for library in libraries:
                if library == "snt" and local_snt and "fast" not in local_snt_tracks:
                    continue
                value, sigma = evaluate(library, operation)
                interval_low, interval_high = max(0.0, value-sigma), value+sigma
                mapped_low = max(lower_input, interval_low**2)
                mapped_high = min(upper_input, interval_high**2)
                fast_coverage = max(0.0, mapped_high-mapped_low)/(upper_input-lower_input)
                append(case, library, f"{library} first-order square-root propagation",
                       value, sigma, reference_sd, draws, out_unit,
                       coverage_target=fast_coverage)
            if local_snt and "snt" in libraries and "monte_carlo" in local_snt_tracks:
                qx = snt(x, sx, snt_input_unit)
                append_snt_monte_carlo(case, [qx], [distribution], lambda sampled: sqrt(sampled),
                                       reference_sd, draws, out_unit)
            if metrolopy_monte_carlo and "metrolopy" in libraries:
                metro_input = metrolopy.gummy(
                    metrolopy.UniformDist(center=x, half_width=half_width), unit=unit
                )
                append_metrolopy_monte_carlo(case, metro_input**0.5,
                                              reference_sd, draws, out_unit)

        elif case == "reciprocal_uniform":
            x = float(get(prefix+"x"))
            sx, unit = float(get(prefix+"standard_deviation")), get(prefix+"unit")
            distribution = get(prefix+"input_distribution")
            if distribution != "uniform":
                raise ValueError(f"{case}.input_distribution must be uniform")
            half_width = math.sqrt(3)*sx
            lower_input, upper_input = x-half_width, x+half_width
            if lower_input <= 0:
                raise ValueError(f"{case} denominator support must remain strictly positive")
            draws = 1/rng.uniform(lower_input, upper_input, samples)
            output_mean = math.log(upper_input/lower_input)/(upper_input-lower_input)
            output_second_moment = 1/(lower_input*upper_input)
            reference_sd = math.sqrt(output_second_moment-output_mean*output_mean)
            def operation(which):
                if which == "snt": return 1/snt(x, sx, unit)
                if which == "pint": return 1/registry.Quantity(ufloat(x, sx), unit)
                return 1/metrolopy.gummy(x, u=sx, unit=unit)
            for library in libraries:
                if library == "snt" and local_snt and "fast" not in local_snt_tracks:
                    continue
                value, sigma = evaluate(library, operation)
                interval_low, interval_high = max(0.0, value-sigma), value+sigma
                mapped_low = max(lower_input, 1/interval_high)
                mapped_high = min(upper_input, 1/interval_low) if interval_low > 0 else upper_input
                fast_coverage = max(0.0, mapped_high-mapped_low)/(upper_input-lower_input)
                append(case, library, f"{library} first-order reciprocal propagation",
                       value, sigma, reference_sd, draws, f"1/{unit}",
                       coverage_target=fast_coverage)
            if local_snt and "snt" in libraries and "monte_carlo" in local_snt_tracks:
                qx = snt(x, sx, unit)
                append_snt_monte_carlo(case, [qx], [distribution], lambda sampled: 1/sampled,
                                       reference_sd, draws, f"1/{unit}")
            if metrolopy_monte_carlo and "metrolopy" in libraries:
                metro_input = metrolopy.gummy(
                    metrolopy.UniformDist(center=x, half_width=half_width), unit=unit
                )
                append_metrolopy_monte_carlo(case, 1/metro_input,
                                              reference_sd, draws, f"1/{unit}")

        elif case == "correlated_addition":
            x, sx = float(get(prefix+"x")), float(get(prefix+"sigma_x"))
            y, sy = float(get(prefix+"y")), float(get(prefix+"sigma_y"))
            rho, unit = float(get(prefix+"correlation")), get(prefix+"unit")
            covariance = rho*sx*sy
            draws = rng.multivariate_normal([x, y], [[sx*sx, covariance], [covariance, sy*sy]], samples).sum(axis=1)
            reference_sd = math.sqrt(sx*sx+sy*sy+2*covariance)
            for library in libraries:
                if library == "snt" and local_snt and "fast" not in local_snt_tracks:
                    continue
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
            if local_snt and "snt" in libraries and "monte_carlo" in local_snt_tracks:
                qx, qy = snt(x, sx, unit), snt(y, sy, unit)
                Quantity.correlate(qx, qy, rho)
                append_snt_monte_carlo(case, [qx, qy], ["normal", "normal"],
                                       lambda left, right: left + right,
                                       reference_sd, draws, unit)

        elif case == "rectangular_linear":
            x = float(get(prefix+"x"))
            sx, unit = float(get(prefix+"standard_deviation")), get(prefix+"unit")
            half_width = math.sqrt(3)*sx
            draws = rng.uniform(x-half_width, x+half_width, samples)
            reference_sd = sx
            for library in libraries:
                if library == "snt" and local_snt and "fast" not in local_snt_tracks:
                    continue
                def operation(which):
                    if which == "snt": return snt(x, sx, unit)
                    if which == "pint": return registry.Quantity(ufloat(x, sx), unit)
                    return metrolopy.gummy(x, u=sx, unit=unit)
                value, sigma = evaluate(library, operation)
                model = f"{library} first-order from standard deviation"
                append(case, library, model, value, sigma, reference_sd, draws, unit,
                       coverage_target=1/math.sqrt(3))
            if local_snt and "snt" in libraries and "monte_carlo" in local_snt_tracks:
                qx = snt(x, sx, unit)
                append_snt_monte_carlo(case, [qx], ["uniform"], lambda sampled: sampled,
                                       reference_sd, draws, unit)

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
    plot_libraries = list(libraries)
    for mc_track, fast_track in (("snt_mc", "snt"), ("metrolopy_mc", "metrolopy")):
        if mc_track in set(valid.library):
            if fast_track in plot_libraries:
                plot_libraries.insert(plot_libraries.index(fast_track) + 1, mc_track)
            else:
                plot_libraries.append(mc_track)
    width = 0.8/max(1, len(plot_libraries))
    x = np.arange(len(case_order))
    colors = {"snt": "#1878a5", "snt_mc": "#56a6c8", "pint": "#d87524",
              "metrolopy": "#568a45", "metrolopy_mc": "#90b878"}
    fig, (ax, coverage_ax) = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    for index, library in enumerate(plot_libraries):
        subset = valid[valid.library == library].set_index("case_id").reindex(case_order)
        offset = (index-(len(plot_libraries)-1)/2)*width
        package = "snt" if library == "snt_mc" else "metrolopy" if library == "metrolopy_mc" else library
        version = get(f"packages.{package}.version")
        if package == "snt" and local_snt:
            version = f"{scinumtools3.__version__} local"
        label = (f"SNT3 Monte Carlo track {version}" if library == "snt_mc" else
                 f"SNT3 fast track {version}" if library == "snt" else
                 f"MetroloPy Monte Carlo track {version}" if library == "metrolopy_mc" else
                 f"MetroloPy fast track {version}" if library == "metrolopy" else
                 f"{library} {version}")
        ax.bar(x+offset, subset.reported_uncertainty/subset.monte_carlo_sd, width,
               color=colors.get(library), label=label)
    ax.axhline(1, color="black", linewidth=1, label="Monte Carlo standard deviation")
    ax.set_ylabel("reported uncertainty / Monte Carlo SD")
    ax.set_title(f"Uncertainty spread relative to seeded Monte Carlo · n={samples:,}")
    ax.grid(axis="y", alpha=.25)
    coverage_ax.axhline(one_sigma_coverage*100, color="black", linestyle="--", linewidth=1,
                        label="Normal ±1σ reference (68.27%)")
    if any(track in plot_libraries for track in ("snt_mc", "metrolopy_mc")):
        coverage_ax.axhline(float(get("semantics.normal_coverage"))*100, color="#666666",
                            linestyle=":", linewidth=1, label="Configured central MC interval target")
    coverage_ax.set_ylabel("interval coverage (%)")
    case_labels = {
        "linear_conversion": "temperature conversion", "addition": "addition",
        "product": "product", "reciprocal": "reciprocal",
        "reciprocal_uniform": "reciprocal (uniform)",
        "square_nonlinear": "square (nonlinear)",
        "sqrt_uniform_boundary": "sqrt (boundary)",
        "correlated_addition": "correlated addition",
        "rectangular_linear": "uniform input",
    }
    coverage_ax.set_xticks(x, [case_labels[case] for case in case_order], rotation=12, ha="right")
    coverage_ax.grid(axis="y", alpha=.25)
    uniform_targets = valid[
        valid.case_id.isin(("reciprocal_uniform", "sqrt_uniform_boundary", "rectangular_linear"))
        & valid.library.isin(("snt", "pint", "metrolopy"))
    ].groupby("case_id").coverage_target.mean()
    if not uniform_targets.empty:
        target_x = [x[case_order.index(case)] for case in uniform_targets.index if case in case_order]
        target_y = [uniform_targets[case]*100 for case in uniform_targets.index if case in case_order]
        coverage_ax.scatter(target_x, target_y, marker="D", s=24, color="#333333",
                            label="Analytic expected coverage for uniform fast tracks", zorder=5)
    for index, library in enumerate(plot_libraries):
        subset = valid[valid.library == library].set_index("case_id").reindex(case_order)
        offset = (index-(len(plot_libraries)-1)/2)*width
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
                             min(1, max(upper_bound, one_sigma_coverage,
                                        float(get("semantics.normal_coverage"))
                                        if any(track in plot_libraries for track in ("snt_mc", "metrolopy_mc"))
                                        else 0)+0.03)*100)
    handles, labels = ax.get_legend_handles_labels()
    coverage_handles, coverage_labels = coverage_ax.get_legend_handles_labels()
    handles.extend(coverage_handles)
    labels.extend(coverage_labels)
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.98),
               fontsize=8, ncol=min(3, len(handles)))
    fig.subplots_adjust(top=0.82, bottom=0.23, hspace=0.12, left=0.12, right=0.98)
    fig.savefig(args.figure, dpi=int(get("execution.figure_dpi")))
    plt.close(fig)
    print(frame[["case_id", "library", "status", "reported_uncertainty", "reference_standard_deviation",
                 "monte_carlo_sd", "mc_coverage", "coverage_target", "coverage_minus_target",
                 "nominal_minus_mc_mean"]].to_string(index=False))


if __name__ == "__main__":
    main()
