"""Command-line entry point.

Subcommands:
    run             Run the full pipeline (load -> validate -> split ->
                     catalogs -> retrieval -> thresholds -> metrics ->
                     review export -> report) from a YAML config.
    smoke-test      Shortcut for `run --config configs/pilot_toy.yaml`.
    validate        Load a dataset and print the validation report only.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from tool_routing.data.schema import Request, Tool
from tool_routing.data.toy_fixture import load_distractor_pool_tools, load_toy_dataset
from tool_routing.data.validate import validate_dataset
from tool_routing.evaluation.metrics import (
    compute_metrics,
    query_grouped_bootstrap_ci,
    risk_coverage_curve,
)
from tool_routing.evaluation.pipeline import run_predictions
from tool_routing.evaluation.records import PredictionRecord
from tool_routing.evaluation.thresholds import (
    ALWAYS_TOP1,
    MARGIN_THRESHOLD,
    SCORE_THRESHOLD,
    AbstentionPolicy,
    select_threshold,
)
from tool_routing.reporting.report import plot_risk_coverage, render_markdown_report
from tool_routing.reporting.review_export import build_review_row, export_review_csv
from tool_routing.reporting.run_metadata import write_run_metadata
from tool_routing.retrieval.bm25 import BM25Retriever
from tool_routing.retrieval.embeddings import EmbeddingRetriever
from tool_routing.scenarios.catalog import ORIGINAL, DistractorPicker
from tool_routing.scenarios.splits import make_pilot_splits


def _load_toy() -> tuple[list[Tool], list[Request], list[Tool]]:
    tools, requests = load_toy_dataset()
    distractor_pool = load_distractor_pool_tools()
    return tools, requests, distractor_pool


def _load_toolret(cfg: dict) -> tuple[list[Tool], list[Request], list[Tool], dict[str, set[str]]]:
    """Load ToolRet tools/requests and determine each query subset's actual
    tool-family pool.

    The ToolRet-Tools corpus groups tools into just three coarse buckets
    (code/customized/web) and the per-tool ID prefixes (e.g. "apibank",
    "gorilla_huggingface", "tool_be_honest") do NOT reliably match the
    ToolRet-Queries subset name strings (e.g. "gorilla-huggingface" uses a
    hyphen; "tool-be-honest" vs "tool_be_honest"; some subsets like
    "autotools-*" map to a differently-named "webtools_*" family). So
    instead of guessing a name mapping, we look at which tool_family values
    are *actually* referenced by each subset's annotated valid tools, and
    use that as the subset's catalog pool. This is exact (derived from the
    real labels), not a name heuristic.
    """
    from tool_routing.data.toolret_adapter import load_toolret_requests, load_toolret_tools

    raw_dir = cfg["toolret"]["raw_dir"]
    subsets = cfg["toolret"]["subsets"]
    all_tools_by_id = load_toolret_tools(raw_dir)
    requests, warnings = load_toolret_requests(raw_dir, subsets)
    for w in warnings:
        print(f"[warn] {w}", file=sys.stderr)

    subset_families: dict[str, set[str]] = {s: set() for s in subsets}
    for r in requests:
        subset = r.raw.get("subset")
        if subset not in subset_families:
            continue
        for tid in r.known_valid_tool_ids:
            tool = all_tools_by_id.get(tid)
            if tool is not None and tool.tool_family:
                subset_families[subset].add(tool.tool_family)

    used_families: set[str] = set()
    for fams in subset_families.values():
        used_families |= fams

    pool_tools = [t for t in all_tools_by_id.values() if t.tool_family in used_families]
    held_out_tools = [t for t in all_tools_by_id.values() if t.tool_family not in used_families]
    return pool_tools, requests, held_out_tools, subset_families


def _toolret_pool_fn_factory(tools_by_id: dict[str, Tool], subset_families: dict[str, set[str]]):
    by_family: dict[str, list[str]] = {}
    for t in tools_by_id.values():
        if t.tool_family:
            by_family.setdefault(t.tool_family, []).append(t.tool_id)

    def pool_fn(request: Request) -> list[str]:
        subset = request.raw.get("subset")
        families = subset_families.get(subset, set())
        ids: list[str] = []
        for fam in families:
            ids.extend(by_family.get(fam, []))
        return ids

    return pool_fn


def _pool_fn_factory(tools_by_id: dict[str, Tool]):
    by_source: dict[str, list[str]] = {}
    for t in tools_by_id.values():
        by_source.setdefault(t.source_dataset, []).append(t.tool_id)

    def pool_fn(request: Request) -> list[str]:
        return by_source.get(request.source_dataset, [])

    return pool_fn


def cmd_validate(args: argparse.Namespace) -> None:
    if args.dataset == "toy":
        tools, requests, _ = _load_toy()
    else:
        cfg = yaml.safe_load(Path(args.config).read_text())
        tools, requests, _, _ = _load_toolret(cfg)
    report = validate_dataset(tools, requests)
    print(report.summary())
    if not report.is_clean:
        print("\nDataset has validation issues (see above); see docs/dataset.md.")


def _run_pipeline(cfg: dict) -> None:
    seed = cfg.get("seed", 42)
    out_dir = Path(cfg["output_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    subset_families: dict[str, set[str]] | None = None
    if cfg["dataset"] == "toy":
        pool_tools, requests, held_out_tools = _load_toy()
    elif cfg["dataset"] == "toolret":
        pool_tools, requests, held_out_tools, subset_families = _load_toolret(cfg)
    else:
        raise ValueError(f"Unknown dataset: {cfg['dataset']!r}")

    tools_by_id = {t.tool_id: t for t in pool_tools}
    # Retrieval needs to resolve distractor tool IDs too, even though they
    # are not part of any query's "original" pool.
    all_tools_by_id = {**tools_by_id, **{t.tool_id: t for t in held_out_tools}}

    validation = validate_dataset(pool_tools, requests)
    (out_dir / "validation_report.txt").write_text(validation.summary())
    print("Validation:\n" + validation.summary())

    pilot_cfg = cfg.get("pilot", {})
    split_manifest = make_pilot_splits(
        requests,
        tools_by_id,
        seed=seed,
        max_total=pilot_cfg.get("max_total_queries", 500),
        dev_frac=pilot_cfg.get("dev_frac", 0.6),
        val_frac=pilot_cfg.get("val_frac", 0.2),
    )
    (out_dir / "splits.json").write_text(json.dumps(split_manifest.to_dict(), indent=2))
    if split_manifest.family_overlap_warnings:
        print(
            "[warn] tool families appear in more than one split "
            f"(leakage not ruled out): {split_manifest.family_overlap_warnings}"
        )

    kept_ids = set(split_manifest.dev_query_ids + split_manifest.val_query_ids + split_manifest.test_query_ids)
    requests_by_split = {"dev": [], "val": [], "test": []}
    for r in requests:
        split = split_manifest.split_of(r.query_id)
        if split is not None:
            requests_by_split[split].append(r)
    pilot_requests = [r for r in requests if r.query_id in kept_ids]

    if subset_families is not None:
        pool_fn = _toolret_pool_fn_factory(tools_by_id, subset_families)
    else:
        pool_fn = _pool_fn_factory(tools_by_id)
    distractor_picker = DistractorPicker(held_out_tools) if held_out_tools else None

    emb_cfg = cfg.get("embedding", {})
    retrievers = {
        "bm25": BM25Retriever(),
        "embedding": EmbeddingRetriever(
            model_name=emb_cfg.get("model_name", "sentence-transformers/all-MiniLM-L6-v2"),
            device=emb_cfg.get("device", "cpu"),
            cache_dir=emb_cfg.get("cache_dir", "data/cache/embeddings"),
        ),
    }

    n_distractors = cfg.get("catalog", {}).get("n_distractors", 3)
    predictions, manifests = run_predictions(
        pilot_requests, all_tools_by_id, pool_fn, distractor_picker, retrievers, n_distractors=n_distractors
    )
    retrievers["embedding"].save_cache()
    with open(out_dir / "predictions.jsonl", "w") as f:
        for p in predictions:
            f.write(json.dumps(p.to_dict()) + "\n")
    with open(out_dir / "catalog_manifests.jsonl", "w") as f:
        for m in manifests:
            f.write(json.dumps(m.to_dict()) + "\n")

    predictions_by_split: dict[str, list[PredictionRecord]] = {"dev": [], "val": [], "test": []}
    for p in predictions:
        split = split_manifest.split_of(p.query_id)
        if split is not None:
            predictions_by_split[split].append(p)

    max_risk = cfg.get("thresholds", {}).get("max_risk", 0.1)
    frozen_policies: dict[str, dict[str, AbstentionPolicy]] = {}
    metrics_table: dict[tuple, dict] = {}
    curves_by_method: dict[str, list[dict]] = {}

    for method in retrievers:
        val_records = [p for p in predictions_by_split["val"] if p.method == method]
        test_records = [p for p in predictions_by_split["test"] if p.method == method]

        policies = {
            ALWAYS_TOP1: AbstentionPolicy(ALWAYS_TOP1),
            SCORE_THRESHOLD: select_threshold(val_records, SCORE_THRESHOLD, max_risk=max_risk),
            MARGIN_THRESHOLD: select_threshold(val_records, MARGIN_THRESHOLD, max_risk=max_risk),
        }
        frozen_policies[method] = policies

        thresholds_for_curve = sorted({r.top1_score for r in test_records if r.top1_score is not None})
        curve_records = test_records if test_records else val_records
        curves_by_method[method] = risk_coverage_curve(
            curve_records, SCORE_THRESHOLD, [float("-inf")] + thresholds_for_curve
        )

        for policy_name, policy in policies.items():
            for scenario in sorted({p.scenario for p in test_records}) or [ORIGINAL]:
                scenario_records = [r for r in test_records if r.scenario == scenario]
                metrics = compute_metrics(scenario_records, policy)
                ci = query_grouped_bootstrap_ci(
                    scenario_records,
                    policy,
                    lambda recs, pol: compute_metrics(recs, pol).selective_risk,
                    n_resamples=200,
                    seed=seed,
                )
                record = metrics.to_dict()
                record["selective_risk_ci"] = ci
                metrics_table[(method, scenario, policy_name)] = record

    (out_dir / "thresholds.json").write_text(
        json.dumps(
            {m: {k: {"kind": p.kind, "threshold": p.threshold} for k, p in pol.items()} for m, pol in frozen_policies.items()},
            indent=2,
        )
    )
    with open(out_dir / "metrics.json", "w") as f:
        json.dump({"::".join(k): v for k, v in metrics_table.items()}, f, indent=2)

    plot_path = out_dir / "risk_coverage.png"
    plot_risk_coverage(curves_by_method, plot_path)

    review_rows = []
    manifests_by_query_scenario = {(m.query_id, m.scenario): m for m in manifests}
    bm25_by_key = {(p.query_id, p.scenario): p for p in predictions if p.method == "bm25"}
    emb_by_key = {(p.query_id, p.scenario): p for p in predictions if p.method == "embedding"}
    for r in pilot_requests:
        if split_manifest.split_of(r.query_id) != "test":
            continue
        for scenario in (ORIGINAL,):
            key = (r.query_id, scenario)
            manifest = manifests_by_query_scenario.get(key)
            bm25_pred = bm25_by_key.get(key)
            emb_pred = emb_by_key.get(key)
            if manifest is None or bm25_pred is None or emb_pred is None:
                continue
            review_rows.append(
                build_review_row(
                    query_id=r.query_id,
                    query_text=r.query_text,
                    scenario=scenario,
                    catalog_id=manifest.catalog_id,
                    known_valid_tool_ids=list(r.known_valid_tool_ids),
                    bm25_top_tool_ids=list(bm25_pred.top_k_tool_ids[:3]),
                    bm25_top_descriptions=[tools_by_id[t].description for t in bm25_pred.top_k_tool_ids[:3] if t in tools_by_id],
                    embedding_top_tool_ids=list(emb_pred.top_k_tool_ids[:3]),
                    embedding_top_descriptions=[tools_by_id[t].description for t in emb_pred.top_k_tool_ids[:3] if t in tools_by_id],
                    answerability_status=r.answerability_review_status if r.answerability_review_status != "unreviewed" else "uncertain",
                )
            )
    export_review_csv(review_rows, out_dir / "review.csv")

    write_run_metadata(out_dir / "run_metadata.json", cfg, seed)

    limitations = [
        "known_valid_tool_ids is a known-incomplete positive label set; 'incorrect' means "
        "'outside the annotated label set', not 'confirmed wrong'.",
        "answerability_review_status is 'unreviewed' for essentially all queries in this "
        "milestone; false-action-rate and abstention-rate-on-answerable are only meaningful "
        "on an audited subset (see docs/review_workflow.md) and may show as n/a here.",
        "Catalogs are built per source subset (reduced-catalog pilot), not the official "
        "full ToolRet corpus; see docs/dataset.md.",
        "Tool-family leakage across dev/val/test is only diagnosed (see splits.json "
        "family_overlap_warnings), not enforced.",
        "Distractor tools are selected by BM25 lexical similarity to the query text, a cheap "
        "proxy for semantic similarity, not a verified one.",
    ]
    hypotheses = [
        "A compact fine-tuned/trained neural retriever could reduce incorrect selections "
        "under catalog changes relative to these frozen baselines -- NOT tested here.",
        "Combining BM25 and embedding scores could improve abstention quality -- NOT tested here.",
    ]
    report_md = render_markdown_report(
        title=f"Tool routing pilot report: {cfg.get('run_name', 'unnamed')}",
        run_metadata=json.loads((out_dir / "run_metadata.json").read_text()),
        dataset_summary={
            "dataset": cfg["dataset"],
            "n_tools": len(tools_by_id),
            "n_requests_total": len(requests),
            "n_requests_in_pilot": len(pilot_requests),
        },
        split_summary=split_manifest.to_dict()
        | {"dev": len(split_manifest.dev_query_ids), "val": len(split_manifest.val_query_ids), "test": len(split_manifest.test_query_ids)},
        metrics_by_method_scenario=metrics_table,
        limitations=limitations,
        hypotheses_not_yet_tested=hypotheses,
        plot_relative_path=plot_path.name,
        error_analysis_samples=_error_analysis_sample(predictions_by_split["test"], tools_by_id),
    )
    (out_dir / "REPORT.md").write_text(report_md)
    print(f"\nWrote outputs to {out_dir}/ (see REPORT.md)")


def _error_analysis_sample(records: list[PredictionRecord], tools_by_id: dict[str, Tool], n: int = 5) -> list[dict]:
    wrong = [r for r in records if r.is_top1_correct() is False and r.scenario == ORIGINAL]
    sample = wrong[:n]
    out = []
    for r in sample:
        out.append(
            {
                "query_id": r.query_id,
                "scenario": r.scenario,
                "predicted": r.top1_tool_id(),
                "known_valid_tool_ids": list(r.known_valid_tool_ids),
                "note": f"method={r.method}",
            }
        )
    return out


def cmd_run(args: argparse.Namespace) -> None:
    cfg = yaml.safe_load(Path(args.config).read_text())
    if args.output_dir:
        cfg["output_dir"] = args.output_dir
    _run_pipeline(cfg)


def cmd_smoke_test(args: argparse.Namespace) -> None:
    cfg = yaml.safe_load(Path("configs/pilot_toy.yaml").read_text())
    _run_pipeline(cfg)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="tool-routing")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Run the full pipeline from a YAML config.")
    p_run.add_argument("--config", required=True)
    p_run.add_argument("--output-dir", default=None)
    p_run.set_defaults(func=cmd_run)

    p_smoke = sub.add_parser("smoke-test", help="Run the toy end-to-end smoke test.")
    p_smoke.set_defaults(func=cmd_smoke_test)

    p_validate = sub.add_parser("validate", help="Print a dataset validation report.")
    p_validate.add_argument("--dataset", choices=["toy", "toolret"], default="toy")
    p_validate.add_argument("--config", default="configs/pilot_toolret.yaml")
    p_validate.set_defaults(func=cmd_validate)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
