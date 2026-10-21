"""Risk-coverage plots and the honest Markdown summary report."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


def plot_risk_coverage(curves_by_method: dict[str, list[dict]], out_path: str | Path) -> None:
    """``curves_by_method``: method name -> list of {"coverage", "selective_risk"}."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(6, 4.5))
    for method, curve in curves_by_method.items():
        points = [(p["coverage"], p["selective_risk"]) for p in curve if p["selective_risk"] is not None]
        if not points:
            continue
        points.sort()
        xs, ys = zip(*points)
        ax.plot(xs, ys, marker="o", markersize=3, label=method)
    ax.set_xlabel("Coverage (accepted / evaluated)")
    ax.set_ylabel("Selective risk (incorrect / accepted)")
    ax.set_title("Risk vs. coverage")
    ax.set_xlim(0, 1)
    ax.set_ylim(bottom=0)
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def render_markdown_report(
    *,
    title: str,
    run_metadata: dict,
    dataset_summary: dict,
    split_summary: dict,
    metrics_by_method_scenario: dict,
    limitations: list[str],
    hypotheses_not_yet_tested: list[str],
    plot_relative_path: str | None,
    error_analysis_samples: list[dict] | None = None,
) -> str:
    lines = [f"# {title}", ""]
    lines.append(f"_Generated: {run_metadata.get('generated_at_utc', 'unknown')}_")
    lines.append(f"_Git commit: {run_metadata.get('git_commit', 'unknown')}_")
    lines.append("")
    lines.append(
        "This report describes MEASURED results from the pipeline implemented in "
        "this repository. It is a first milestone (datasets, baselines, evaluation "
        "harness) and does not claim a novel method, publication-readiness, or "
        "generalization beyond what was measured."
    )
    lines.append("")

    lines.append("## Dataset")
    for k, v in dataset_summary.items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")

    lines.append("## Splits")
    for k, v in split_summary.items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")

    lines.append("## Results (measured)")
    lines.append("")
    lines.append(
        "| Method | Scenario | Policy | Coverage | Top-1 agreement with known labels (accepted, not audited-unanswerable) | "
        "Selective Risk | False-action rate (audited unanswerable) | "
        "Abstention rate (audited answerable) | p50 latency (ms) | p95 latency (ms) |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for key, m in metrics_by_method_scenario.items():
        method, scenario, policy = key
        lines.append(
            f"| {method} | {scenario} | {policy} | {m.get('coverage'):.3f} | "
            f"{_fmt(m.get('top1_accuracy'))} | {_fmt(m.get('selective_risk'))} | "
            f"{_fmt(m.get('false_action_rate'))} | {_fmt(m.get('abstention_rate_on_answerable'))} | "
            f"{_fmt(m.get('latency_p50_ms'))} | {_fmt(m.get('latency_p95_ms'))} |"
        )
    lines.append("")
    lines.append(
        "Raw retrieval scores (BM25 term-overlap scores, cosine similarities) are "
        "NOT probabilities. `known_valid_tool_ids` is a known-incomplete positive "
        "label set, so 'incorrect' above means 'not in the annotated label set', "
        "not 'confirmed wrong'. Unanswerable/answerable audits apply only to the "
        "human-reviewed subset (see docs/review_workflow.md)."
    )
    lines.append("")

    if plot_relative_path:
        lines.append("## Risk vs. coverage")
        lines.append(f"![Risk vs coverage]({plot_relative_path})")
        lines.append("")

    if error_analysis_samples:
        lines.append("## Error analysis sample")
        for s in error_analysis_samples:
            lines.append(f"- query `{s.get('query_id')}` ({s.get('scenario')}): "
                         f"predicted `{s.get('predicted')}`, valid=`{s.get('known_valid_tool_ids')}` "
                         f"-- {s.get('note', '')}")
        lines.append("")

    lines.append("## Limitations (measured/known)")
    for item in limitations:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## Hypotheses NOT yet tested in this milestone")
    for item in hypotheses_not_yet_tested:
        lines.append(f"- {item}")
    lines.append("")

    return "\n".join(lines)


def _fmt(v) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, float):
        return f"{v:.3f}"
    return str(v)
