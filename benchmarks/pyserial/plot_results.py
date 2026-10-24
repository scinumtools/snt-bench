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


def plot(rows, output, dpi=300):
    formats = list(dict.fromkeys(row["format"] for row in rows))
    sizes = sorted({int(row["parameters"]) for row in rows})
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
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), layout="constrained")
    for fmt in formats:
        points = sorted((row for row in rows if row["format"] == fmt),
                        key=lambda row: int(row["parameters"]))
        times_ms = [float(row["median_seconds"]) * 1e3 for row in points]
        style = {"marker": "o", "markersize": 5, "linewidth": 2,
                 "linestyle": LINE_STYLES[fmt], "color": COLORS[fmt],
                 "label": parsers[fmt]}
        axes[0].plot([int(row["parameters"]) for row in points], times_ms, **style)
        axes[1].plot([int(row["payload_bytes"]) for row in points], times_ms, **style)
    for ax in axes:
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.grid(which="both", color="#c8cdd3", linewidth=0.6, alpha=0.7)
    axes[0].set_xlabel("Number of scalar parameters")
    axes[0].set_xticks(sizes, labels=[str(size) for size in sizes])
    axes[0].set_ylabel("Median parse time (ms)")
    axes[0].set_title("Parameters vs. parse time")
    axes[1].set_xlabel("Encoded document size (bytes)")
    axes[1].set_ylabel("Median parse time (ms)")
    axes[1].set_title("Payload vs. parse time")
    axes[1].legend(title="Format / implementation version", frameon=False, fontsize=8)
    fig.suptitle("Python parsing of equivalent configuration data")
    fig.savefig(output, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Existing parsing comparison CSV")
    parser.add_argument("--output", type=Path, required=True, help="Output figure path")
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
    plot(rows, args.output, dpi)
    print(f"Figure: {args.output}")


if __name__ == "__main__":
    main()
