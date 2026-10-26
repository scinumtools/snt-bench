"""Place the native CLI and in-process validation plots in one figure."""

import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli-summary", type=Path, required=True,
                        help="Native CLI summary CSV")
    parser.add_argument("--inprocess-summary", type=Path, required=True,
                        help="In-process Python API summary CSV")
    parser.add_argument("--output", type=Path, required=True,
                        help="Combined output figure")
    args = parser.parse_args()

    def read_rows(path):
        with path.open(newline="", encoding="utf-8") as stream:
            return list(csv.DictReader(stream))

    cli_rows = read_rows(args.cli_summary)
    inprocess_rows = read_rows(args.inprocess_summary)
    cli_participants = len(dict.fromkeys(row["participant"] for row in cli_rows))
    inprocess_participants = len(dict.fromkeys(row["participant"] for row in inprocess_rows))
    fig, (cli_ax, inprocess_ax) = plt.subplots(
        1, 2, figsize=(12, 5),
        gridspec_kw={"width_ratios": (cli_participants, inprocess_participants)},
        layout="constrained",
    )

    def draw(ax, rows, value_key, low_key, high_key, title, ylabel):
        participants = list(dict.fromkeys(row["participant"] for row in rows))
        positions = list(range(len(participants)))
        width = 0.19
        for offset, case_class in enumerate(("valid", "invalid")):
            selected = [next((row for row in rows
                              if row["participant"] == participant
                              and row["case_class"] == case_class), None)
                        for participant in participants]
            medians = [float(row[value_key]) if row else float("nan")
                       for row in selected]
            lows = [float(row[low_key]) if row else float("nan")
                    for row in selected]
            highs = [float(row[high_key]) if row else float("nan")
                     for row in selected]
            ax.bar(
                [position + (offset - 0.5) * width for position in positions],
                medians,
                width=width,
                label=f"{case_class.title()} (n={next((row['fixture_count'] for row in selected if row), 0)})",
                color="#0072B2" if case_class == "valid" else "#D55E00",
                yerr=[[median - low for median, low in zip(medians, lows)],
                      [high - median for median, high in zip(medians, highs)]],
                capsize=3,
                error_kw={"linewidth": 0.8},
            )
        labels = [f"{participant}\n{next(row['participant_version'] for row in rows if row['participant'] == participant)}"
                  for participant in participants]
        ax.set_xticks(positions, labels)
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(axis="y", color="#c8cdd3", linewidth=0.6, alpha=0.7)
        ax.set_axisbelow(True)
        ax.legend(frameon=False)

    draw(cli_ax, cli_rows, "median_batch_ms", "min_batch_ms", "max_batch_ms",
         "Native CLI workflows", "Median time for one CLI batch (ms)")
    draw(inprocess_ax, inprocess_rows, "median_ms", "min_ms", "max_ms",
         "In-process Python APIs", "Median API time per batch (ms)")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved figure: {args.output}")


if __name__ == "__main__":
    main()
