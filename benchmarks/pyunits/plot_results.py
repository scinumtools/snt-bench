"""Plot Python unit benchmark timings by input size, operation, and library."""

import argparse
import csv
from collections import defaultdict
import os
from pathlib import Path
import tempfile

_cache_root = Path(tempfile.gettempdir()) / "snt-bench-matplotlib"
(_cache_root / "mpl").mkdir(parents=True, exist_ok=True)
(_cache_root / "xdg").mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_cache_root / "mpl"))
os.environ.setdefault("XDG_CACHE_HOME", str(_cache_root / "xdg"))
os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


BENCHMARK_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = BENCHMARK_DIR / "performance.png"
LIBRARY_ORDER = ("snt", "pint", "unyt", "astropy", "numpy", "sympy")
LIBRARY_LABELS = {
    "snt": "SNT",
    "pint": "Pint",
    "unyt": "unyt",
    "astropy": "Astropy",
    "numpy": "NumPy reference (no units)",
    "sympy": "SymPy",
}
LIBRARY_COLORS = {
    "snt": "#0072B2",
    "pint": "#E69F00",
    "unyt": "#009E73",
    "astropy": "#D55E00",
    "numpy": "#666666",
    "sympy": "#CC79A7",
}
LINE_STYLES = {"numpy": ":"}
MARKERS = {"numpy": "x"}


def operation_label(row):
    if "group" not in row:
        workload = row["workload"].capitalize()
        return f"{workload}: {row['operation'].replace('_', ' ')}"
    if row["group"] == "construction":
        input_label = {"scalar": "scalar", "list": "list", "ndarray": "NumPy array"}[row["input_kind"]]
        return f"Construction ({input_label})"
    if row["group"] == "conversion":
        return f"Conversion: {row['operation']}"
    if row["group"] == "arithmetic":
        return f"Arithmetic: {row['operation']}"
    return f"NumPy: {row['operation']}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True,
                        help="Summary CSV produced by compare.py or matrix.py")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help=f"Figure path (default: {DEFAULT_OUTPUT})")
    args = parser.parse_args()

    grouped = defaultdict(list)
    metadata = None
    seen_numpy_cases = set()
    with args.input.open(newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        matrix_format = "group" in (reader.fieldnames or ())
        for row in reader:
            if matrix_format:
                case_id = row["case_id"]
                baseline = row.get("numpy_median_seconds")
                if baseline and case_id not in seen_numpy_cases:
                    grouped[(operation_label(row), "numpy")].append(
                        (int(row["elements"]), float(baseline) * 1e6)
                    )
                    seen_numpy_cases.add(case_id)
            if row["library"] not in LIBRARY_ORDER:
                continue
            if matrix_format and row["status"] != "PASS":
                continue
            if not matrix_format and row.get("value_check") != "PASS":
                continue
            if matrix_format:
                seconds = row.get("median_seconds")
                elements = row.get("elements")
            else:
                seconds = row.get("seconds_per_iteration")
                elements = row.get("elements_per_iteration")
            if not seconds or not elements:
                continue
            metadata = metadata or row
            grouped[(operation_label(row), row["library"])].append(
                (int(float(elements)), float(seconds) * 1e6)
            )

    if not grouped:
        parser.error(f"No supported library timings found in {args.input}")

    operations = list(dict.fromkeys(label for label, _ in grouped))
    columns = 4
    rows = (len(operations) + columns - 1) // columns
    fig, axes = plt.subplots(rows, columns, figsize=(16, rows * 3.1),
                             layout="constrained", squeeze=False)
    flat_axes = [axis for row in axes for axis in row]
    for index, operation in enumerate(operations):
        ax = flat_axes[index]
        if operation == "Construction (scalar)":
            scalar_libraries = [
                library for library in LIBRARY_ORDER
                if grouped.get((operation, library))
            ]
            scalar_times = [grouped[(operation, library)][0][1] for library in scalar_libraries]
            ax.bar(
                ["NumPy" if library == "numpy" else LIBRARY_LABELS[library]
                 for library in scalar_libraries],
                scalar_times,
                color=[LIBRARY_COLORS[library] for library in scalar_libraries],
                width=0.72,
            )
            ax.set_yscale("log")
            ax.set_xlabel("Library")
            ax.set_title(operation, color="#222222", fontsize=10)
            ax.grid(axis="y", which="major", color="#b8bec7", linewidth=0.75, alpha=0.65)
            ax.grid(axis="y", which="minor", color="#d8dce2", linewidth=0.4, alpha=0.45)
            continue
        for library in LIBRARY_ORDER:
            points = grouped.get((operation, library))
            if not points:
                continue
            points.sort()
            x_values, y_values = zip(*points)
            ax.plot(
                x_values,
                y_values,
                color=LIBRARY_COLORS[library],
                linestyle=LINE_STYLES.get(library, "-"),
                marker=MARKERS.get(library, "o"),
                linewidth=2.6 if library == "snt" else 1.7,
                markersize=4,
                alpha=0.95,
            )
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_title(operation, color="#222222", fontsize=10)
        ticks = sorted({x for library in LIBRARY_ORDER
                        for x, _ in grouped.get((operation, library), ())})
        ax.set_xticks(ticks, labels=["scalar" if x == 1 else "" if x == 3 and 1 in ticks
                                     else f"{x:g}" for x in ticks])
        ax.grid(which="major", color="#b8bec7", linewidth=0.75, alpha=0.65)
        ax.grid(which="minor", color="#d8dce2", linewidth=0.4, alpha=0.45)

    active_libraries = [
        library for library in LIBRARY_ORDER
        if any(key[1] == library for key in grouped)
    ]
    library_handles = [
        Line2D([0], [0], color=LIBRARY_COLORS[library],
               linestyle=LINE_STYLES.get(library, "-"),
               marker=MARKERS.get(library, "o"), linewidth=2.0, label=LIBRARY_LABELS[library])
        for library in active_libraries
    ]
    if len(operations) % columns:
        legend_ax = flat_axes[len(operations)]
        legend_ax.set_axis_off()
        legend_ax.legend(handles=library_handles, title="Library (color)",
                         loc="center", frameon=False, fontsize=10)
        spare_axes = flat_axes[len(operations) + 1:]
    else:
        fig.legend(handles=library_handles, title="Library (color)",
                   loc="outside lower center", ncols=4, frameon=False, fontsize=9)
        spare_axes = flat_axes[len(operations):]
    for ax in spare_axes:
        ax.set_visible(False)

    fig.suptitle("Python unit library performance by operation and input size", fontsize=15)
    fig.supxlabel("Number of elements (scalar plotted at 1)")
    fig.supylabel("Time per operation (µs)")

    source = metadata.get("snt_source", "unknown")
    snt_version = metadata.get("scinumtools3_version", "unknown")
    python_version = metadata.get("python_version", "unknown")
    fig.text(0.99, 0.006, f"SNT {snt_version} ({source}); Python {python_version}",
             ha="right", va="bottom", fontsize=8, color="#555555")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=300, bbox_inches="tight")
    print(f"Saved figure: {args.output}")


if __name__ == "__main__":
    main()
