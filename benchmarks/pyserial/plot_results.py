"""Render the parsing comparison figure from an existing results CSV."""

import argparse
import csv
import os
from pathlib import Path
import tempfile

_mpl_cache = Path(tempfile.gettempdir()) / "snt-bench-pyserial-matplotlib"
_mpl_cache.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_mpl_cache))
os.environ.setdefault("XDG_CACHE_HOME", str(_mpl_cache))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
DEFAULT_CONFIG = HERE / "config.dip"
COLORS = {"json": "#666666", "yaml": "#0072B2", "toml": "#E69F00", "dipl": "#009E73"}
LINE_STYLES = {"json": "-", "yaml": "--", "toml": ":", "dipl": "-."}


def plot(rows, output, measurement, dpi=300):
    formats = list(dict.fromkeys(row["format"] for row in rows))
    sizes = sorted({int(row["parameters"]) for row in rows})
    measurement_titles = {
        "parser_only": "Native parser output",
        "common_mapping": "Decode to common Python mapping",
    }
    rows = [row for row in rows if row["measurement"] == measurement]
    parsers = {}
    for row in rows:
        fmt = row["format"]
        if fmt == "json":
            parsers[fmt] = f"JSON (stdlib / Python {row['python_version']})"
        elif fmt == "yaml":
            parsers[fmt] = f"YAML ({row['yaml_parser']})"
        elif fmt == "toml":
            parsers[fmt] = f"TOML ({row['toml_parser']})"
        else:
            parsers[fmt] = f"DIPL (SNT3 {row['scinumtools3_version']})"

    output.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 4.5), layout="constrained")
    for fmt in formats:
        points = sorted((row for row in rows if row["format"] == fmt),
                        key=lambda row: int(row["parameters"]))
        if not points:
            continue
        times_ms = [float(row["median_seconds"]) * 1e3 for row in points]
        style = {"marker": "o", "markersize": 5, "linewidth": 1.8,
                 "linestyle": LINE_STYLES[fmt], "color": COLORS[fmt],
                 "label": parsers[fmt]}
        ax.plot([int(row["parameters"]) for row in points], times_ms, **style)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Number of scalar parameters")
    ax.set_xticks(sizes, labels=[str(size) for size in sizes])
    ax.set_ylabel("Median time (ms)")
    ax.set_title(measurement_titles[measurement])
    ax.grid(which="both", color="#c8cdd3", linewidth=0.6, alpha=0.7)
    ax.legend(title="Parser / pinned version", frameon=False, fontsize=8)
    fig.suptitle("Python parsing of equivalent configuration data")
    fig.savefig(output, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Existing parsing comparison CSV")
    parser.add_argument("--output", type=Path, required=True,
                        help="Parser-only figure path; common-mapping figure is written beside it")
    args = parser.parse_args()
    with args.input.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        parser.error(f"No result rows found in {args.input}")
    from scinumtools3.dip import DIP

    dip = DIP()
    dip.add_file(DEFAULT_CONFIG)
    settings = dip.parse()
    dpi = settings["pyserial.execution.outputs.figure_dpi"].value
    common_output = args.output.with_name(args.output.stem + "_common_mapping" + args.output.suffix)
    plot(rows, args.output, "parser_only", dpi)
    plot(rows, common_output, "common_mapping", dpi)
    print(f"Parser-only figure: {args.output}")
    print(f"Common-mapping figure: {common_output}")


if __name__ == "__main__":
    main()
