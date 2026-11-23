#!/usr/bin/env python3
"""Plot mean experiment metrics by optimal depth, strategy and parameter."""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import defaultdict
from dataclasses import dataclass
from itertools import cycle
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools.run_experiments import COLUMNS, ORDERS  # noqa: E402

STRATEGIES = {
    "bfs": "BFS", "dfs": "DFS", "idfs": "IDFS",
    "bf": "Best-first", "astar": "A*", "sma": "SMA*",
}
HEURISTICS = ("h0 Zero", "h1 Hamming", "h2 Manhattan", "h3 Linear conflict")
COLORS = ("#0072b2", "#bf4700", "#008269", "#ac4f83",
          "#76559e", "#8b6200", "#327f9a", "#424c5c")
MARKERS = ("o", "s", "^", "D", "P", "v", "X", "h")
DASHES = ("-", "--", "-.", ":", "--", "-", "-.", ":")
INK = "#16253a"
MUTED = "#475971"
Point = tuple[str, str | None, int]


@dataclass(frozen=True)
class Metric:
    """CSV field and presentation settings for one metric."""

    field: str
    title: str
    units: str
    log: bool = False


METRICS = (
    Metric("solution_length", "Solution length", "moves"),
    Metric("visited_states", "Generated nodes", "nodes per attempt", True),
    Metric("processed_states", "Expanded nodes", "nodes per attempt", True),
    Metric("max_depth_reached", "Maximum search depth", "moves from the start"),
    Metric("peak_stored_states", "Peak storage", "states or SMA* nodes per attempt", True),
    Metric("time_ms", "Search time", "ms per attempt", True),
)


@dataclass(frozen=True)
class Data:
    """Grouped per-attempt means in METRICS order and their data coverage."""

    means: dict[Point, tuple[float, ...]]
    depths: tuple[int, ...]
    coverage: str


def load_data(path: Path) -> Data:
    """Compute means from solved, verified attempts in the contract CSV."""
    groups = defaultdict(list)
    puzzles = set()
    dimensions = set()
    depths = set()
    attempts = 0
    with path.open(encoding="utf-8", newline="") as stream:
        rows = csv.DictReader(stream)
        if tuple(rows.fieldnames or ()) != COLUMNS:
            raise ValueError("CSV header does not match CONTRACT.md section 10.3")
        for row in rows:
            if row["result"] != "solved" or row["verified"] != "true":
                continue
            strategy, param = row["strategy"], row["param"]
            if strategy not in STRATEGIES:
                raise ValueError(f"unknown strategy {strategy!r}")
            depth = int(row["depth"])
            values = tuple(float(row[metric.field]) for metric in METRICS)
            if any(not math.isfinite(value) or value < 0 for value in values):
                raise ValueError(f"invalid metric at CSV row {rows.line_num}")
            groups[strategy, param, depth].append(values)
            groups[strategy, None, depth].append(values)
            puzzles.add(row["puzzle"])
            dimensions.add((int(row["rows"]), int(row["cols"])))
            depths.add(depth)
            attempts += 1
    if not attempts:
        raise ValueError("no solved, verified attempts to plot")
    means = {
        group: tuple(math.fsum(values) / len(trials) for values in zip(*trials))
        for group, trials in groups.items()
    }
    shapes = ", ".join(f"{rows}×{cols}" for rows, cols in sorted(dimensions))
    coverage = (f"{shapes} boards  |  {len(puzzles):,} puzzles  |  "
                f"{attempts:,} verified attempts  |  optimal depths {min(depths)}–{max(depths)}")
    return Data(means, tuple(sorted(depths)), coverage)


def _zero_level(data: Data, index: int) -> float | None:
    values = [point[index] for point in data.means.values()]
    if METRICS[index].log and 0 in values:
        return min((value for value in values if value > 0), default=1.0) / 2
    return None


def _axes(ax, depths: tuple[int, ...], metric: Metric) -> None:
    ax.set_xticks(depths)
    ax.set_xlim(min(depths) - 0.23, max(depths) + 0.23)
    ax.grid(axis="y", color="#dfe6ee", linewidth=0.8)
    ax.set_axisbelow(True)
    if metric.log:
        ax.set_yscale("log")
    if metric.field == "solution_length":
        ax.plot(depths, depths, color="#8290a1", linestyle=":", linewidth=1.15, zorder=1)


def _series(ax, data: Data, index: int, strategy: str, param: str | None,
            label: str, style: tuple[str, str, str], zero_level: float | None):
    values = [
        data.means[strategy, param, d][index] if (strategy, param, d) in data.means else math.nan
        for d in data.depths
    ]
    color, marker, dash = style
    shown = [math.nan if zero_level is not None and value == 0 else value for value in values]
    line, = ax.plot(data.depths, shown, color=color, marker=marker, linestyle=dash,
                    linewidth=1.55, markersize=4.5, label=label, alpha=0.88)
    if zero_level is not None:
        zero_depths = [d for d, value in zip(data.depths, values) if value == 0]
        ax.scatter(zero_depths, [zero_level] * len(zero_depths), marker="v",
                   facecolors="none", edgecolors=color, s=32, zorder=4)
    return line


def _labels(fig, data: Data, metric: Metric, title: str, x: float,
            zero_level: float | None) -> None:
    fig.text(x, 0.952, title, fontweight="bold", fontsize=19, va="top", color=INK)
    fig.text(x, 0.889, data.coverage, fontsize=10.5, va="top", color=MUTED)
    note = "Arithmetic means from results.csv."
    if metric.field == "solution_length":
        note += "  The dotted diagonal marks optimal length."
    if zero_level is not None:
        note += "  Hollow triangles mark zero means below the smallest positive mean."
    fig.text(x, 0.035, note, fontsize=8.5, color=MUTED)


def _strategies(data: Data, index: int):
    metric = METRICS[index]
    zero = _zero_level(data, index)
    fig, ax = plt.subplots(figsize=(9.4, 5.8))
    fig.subplots_adjust(left=0.13, right=0.965, bottom=0.16, top=0.76)
    _axes(ax, data.depths, metric)
    styles = zip(COLORS, MARKERS, DASHES)
    for (key, name), style in zip(STRATEGIES.items(), styles):
        if any((key, None, depth) in data.means for depth in data.depths):
            _series(ax, data, index, key, None, name, style, zero)
    fig.legend(*ax.get_legend_handles_labels(), loc="upper center",
               bbox_to_anchor=(0.54, 0.83), ncols=6, frameon=False)
    ax.set_xlabel("Optimal depth (moves)")
    ax.set_ylabel(f"Mean {metric.title.lower()} ({metric.units})")
    _labels(fig, data, metric, f"{metric.title} by strategy", 0.13, zero)
    return fig


def _parameters(data: Data, index: int):
    metric = METRICS[index]
    zero = _zero_level(data, index)
    fig, axes = plt.subplots(2, 3, figsize=(13.8, 8.2), sharex=True, sharey=True)
    fig.subplots_adjust(left=0.09, right=0.975, bottom=0.25, top=0.818, hspace=0.33, wspace=0.17)
    legends = ({}, {})
    for i, (ax, (key, name)) in enumerate(zip(axes.flat, STRATEGIES.items())):
        params = {p for strategy, p, _ in data.means if strategy == key and p is not None}
        if not params:
            ax.set_axis_off()
            continue
        order = ORDERS if i < 3 else tuple(str(p) for p in range(4))
        params = [p for p in order if p in params] + sorted(params - set(order))
        _axes(ax, data.depths, metric)
        ax.set_title(name, loc="left", fontweight="bold", color=INK)
        styles = dict(zip(order, zip(COLORS, MARKERS, DASHES)))
        extra_styles = cycle(zip(COLORS, MARKERS, DASHES))
        legend = legends[i // 3]
        for param in params:
            style = styles.get(param) or next(extra_styles)
            label = HEURISTICS[int(param)] if i >= 3 and param in order else param
            legend[label] = _series(ax, data, index, key, param, label, style, zero)
    for legend, y, columns in zip(legends, (0.151, 0.106), (8, 4)):
        if legend:
            fig.legend(list(legend.values()), list(legend), loc="upper center",
                       bbox_to_anchor=(0.53, y), ncols=columns, frameon=False)
    fig.supxlabel("Optimal depth (moves)", x=0.53, y=0.176, color=INK)
    fig.supylabel(f"Mean {metric.title.lower()} ({metric.units})", x=0.018, color=INK)
    _labels(fig, data, metric, f"{metric.title} by order or heuristic", 0.09, zero)
    return fig


def render(data: Data, output: Path) -> None:
    """Write both figure layouts per metric as PNG and vector PDF."""
    output.mkdir(parents=True, exist_ok=True)
    with plt.rc_context({
        "font.family": "DejaVu Sans", "font.size": 10, "figure.facecolor": "white",
        "text.color": INK, "axes.labelcolor": INK, "axes.edgecolor": "#a3afbd",
        "axes.spines.top": False, "axes.spines.right": False,
        "xtick.color": MUTED, "ytick.color": MUTED, "pdf.fonttype": 42,
    }):
        for index, metric in enumerate(METRICS):
            for name, layout in (("strategies", _strategies), ("parameters", _parameters)):
                fig = layout(data, index)
                try:
                    stem = f"{metric.field}_{name}"
                    fig.savefig(output / f"{stem}.png", dpi=180)
                    fig.savefig(output / f"{stem}.pdf",
                                metadata={"Title": metric.title, "CreationDate": None})
                finally:
                    plt.close(fig)


def main() -> int:
    """Regenerate the report figures from a benchmark CSV."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=ROOT / "results" / "results.csv")
    parser.add_argument("--out", type=Path, default=ROOT / "report" / "figures")
    args = parser.parse_args()
    try:
        data = load_data(args.csv)
        render(data, args.out)
    except (OSError, ValueError, TypeError, csv.Error) as exc:
        parser.exit(2, f"plot.py: {exc}\n")
    print(f"Wrote {len(METRICS) * 4} figure files to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
