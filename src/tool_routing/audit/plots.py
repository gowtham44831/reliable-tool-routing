"""Score / margin distribution plots, split by label agreement."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from tool_routing.evaluation.records import PredictionRecord  # noqa: E402
from tool_routing.scenarios.catalog import KNOWN_REMOVED  # noqa: E402

GROUPS = (
    ("top-1 in labels (original + distractors_added)", "tab:green"),
    ("top-1 not in labels (original + distractors_added)", "tab:red"),
    ("known_removed (no label left in catalog; all 'incorrect' by construction)", "tab:gray"),
)


def _group(r: PredictionRecord) -> int:
    if r.scenario == KNOWN_REMOVED:
        return 2
    return 0 if r.is_top1_correct() else 1


def plot_signal_distributions(
    records_by_split: dict[str, list[PredictionRecord]],
    method: str,
    thresholds: dict[str, float],
    out_path: str | Path,
) -> None:
    """2x2 grid: rows = (top-1 score, top1-top2 margin), cols = splits.

    ``thresholds`` maps 'score'/'margin' to the frozen threshold, drawn as
    a vertical line (accept iff value >= line).
    """
    splits = list(records_by_split)
    fig, axes = plt.subplots(2, len(splits), figsize=(6 * len(splits), 8), squeeze=False)
    for col, split in enumerate(splits):
        recs = [r for r in records_by_split[split] if r.method == method]
        for row, (signal, label) in enumerate((("score", "top-1 score"), ("margin", "top1 - top2 margin"))):
            ax = axes[row][col]
            vals = [
                (r.top1_score if signal == "score" else r.margin, _group(r))
                for r in recs
            ]
            vals = [(v, g) for v, g in vals if v is not None]
            if not vals:
                ax.set_title(f"{split}: no data")
                continue
            allv = np.array([v for v, _ in vals])
            bins = np.linspace(allv.min(), allv.max(), 31) if allv.max() > allv.min() else 10
            for g, (name, color) in enumerate(GROUPS):
                gv = [v for v, gg in vals if gg == g]
                if gv:
                    ax.hist(gv, bins=bins, histtype="step", linewidth=1.8, color=color,
                            label=f"{name} (n={len(gv)})")
            t = thresholds.get(signal)
            if t is not None and np.isfinite(t):
                ax.axvline(t, color="black", linestyle="--", linewidth=1.2,
                           label=f"frozen threshold = {t:.4g} (selected on val)")
            ax.set_title(f"{method} | {split} | {label}")
            ax.set_xlabel(label)
            ax.set_ylabel("count of (query, scenario) rows")
            ax.legend(fontsize=7)
            ax.grid(alpha=0.3)
    fig.suptitle(
        f"{method}: distributions under the available (known-incomplete) labels. "
        "'Not in labels' is not confirmed wrong.",
        fontsize=10,
    )
    fig.tight_layout()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def plot_val_selection_trace(traces: dict[str, list[dict]], max_risk: float, out_path: str | Path) -> None:
    """Validation risk vs. coverage for every candidate threshold."""
    fig, ax = plt.subplots(figsize=(7, 5))
    for name, trace in traces.items():
        pts = sorted((t["coverage"], t["selective_risk"]) for t in trace if t["selective_risk"] is not None)
        if pts:
            xs, ys = zip(*pts)
            ax.plot(xs, ys, marker=".", markersize=3, linewidth=1, label=name)
    ax.axhline(max_risk, color="black", linestyle="--", linewidth=1, label=f"val risk target {max_risk}")
    ax.set_xscale("symlog", linthresh=0.02)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("validation coverage (symlog scale)")
    ax.set_ylabel("validation selective risk (not in labels / accepted)")
    ax.set_title("Validation-only threshold candidates (all scenarios pooled)")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=130)
    plt.close(fig)
