"""Milestone-2 evaluation audit (diagnostic only; no new method, no tuning).

Reads an EXISTING pilot run directory (read-only; file hashes are checked
before and after so the original outputs are provably preserved) plus the
raw ToolRet files, and writes audit artifacts to a separate directory:

    python scripts/audit_evaluation.py \
        --config configs/pilot_toolret.yaml \
        --pilot-dir results/toolret_pilot \
        --out-dir results/evaluation_audit

See docs/evaluation_audit.md for the interpretation of every output.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import yaml

from tool_routing.audit.bounded_review import build_bounded_review_set, export_bounded_review_set
from tool_routing.audit.catalog_audit import (
    audit_catalogs,
    audit_methods_saw_identical_inputs,
    distractor_selection_breakdown,
    distractor_top1_review_rows,
)
from tool_routing.audit.leakage import _tokens, jaccard, leakage_report
from tool_routing.audit.plots import plot_signal_distributions, plot_val_selection_trace
from tool_routing.audit.review_sample import export_review_sample, stratified_review_sample
from tool_routing.audit.threshold_diagnostics import (
    diagnostics_table,
    explain_threshold,
    paired_accuracy_difference,
    scenario_specific_policies,
    selection_trace,
)
from tool_routing.cli import _load_toolret, _toolret_pool_fn_factory
from tool_routing.evaluation.records import PredictionRecord
from tool_routing.evaluation.thresholds import (
    ALWAYS_TOP1,
    MARGIN_THRESHOLD,
    SCORE_THRESHOLD,
    AbstentionPolicy,
)
from tool_routing.retrieval.embeddings import is_immutable_revision
from tool_routing.scenarios.catalog import DISTRACTORS_ADDED, KNOWN_REMOVED, ORIGINAL
from tool_routing.scenarios.splits import normalize_for_grouping

SPLITS = ("dev", "val", "test")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hash_dir(d: Path) -> dict[str, str]:
    return {p.name: sha256_file(p) for p in sorted(d.iterdir()) if p.is_file()}


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    fields: list[str] = []
    for r in rows:
        fields += [k for k in r if k not in fields]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def fmt(v, nd=3) -> str:
    if v is None:
        return "undef"
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return str(v)


def ci(lo, hi) -> str:
    if lo is None:
        return "undef"
    return f"[{lo:.3f}, {hi:.3f}]"


def md_counts_table(rows: list[dict], split: str) -> list[str]:
    out = [
        "| method | policy | threshold | scenario | n | accepted | correct | incorrect | coverage [95% Wilson] | selective risk [95% Wilson] |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        if r["split"] != split:
            continue
        thr = r["threshold"] if isinstance(r["threshold"], str) else f"{r['threshold']:.4g}"
        out.append(
            f"| {r['method']} | {r['policy']} | {thr} | {r['scenario']} | {r['n_queries']} | {r['n_accepted']} | "
            f"{r['n_correct_accepted']} | {r['n_incorrect_accepted']} | "
            f"{r['n_accepted']}/{r['n_queries']} = {fmt(r['coverage'])} {ci(r['coverage_ci95_low'], r['coverage_ci95_high'])} | "
            f"{r['n_incorrect_accepted']}/{r['n_accepted']} = {fmt(r['selective_risk'])} "
            f"{ci(r['selective_risk_ci95_low'], r['selective_risk_ci95_high'])} |"
        )
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/pilot_toolret.yaml")
    ap.add_argument("--pilot-dir", default="results/toolret_pilot")
    ap.add_argument("--out-dir", default="results/evaluation_audit")
    ap.add_argument("--review-per-subset", type=int, default=20)
    ap.add_argument("--bounded-per-subset", type=int, default=8)
    args = ap.parse_args(argv)

    cfg = yaml.safe_load(Path(args.config).read_text())
    pilot = Path(args.pilot_dir)
    out = Path(args.out_dir)
    if out.resolve() == pilot.resolve():
        sys.exit("--out-dir must differ from --pilot-dir (pilot outputs are preserved read-only)")
    out.mkdir(parents=True, exist_ok=True)
    hashes_before = hash_dir(pilot)

    # ------------------------------------------------------------ load
    pool_tools, requests, held_out_tools, subset_families = _load_toolret(cfg)
    tools_by_id = {t.tool_id: t for t in pool_tools}
    all_tools_by_id = {**tools_by_id, **{t.tool_id: t for t in held_out_tools}}
    requests_by_id = {r.query_id: r for r in requests}
    splits = json.loads((pilot / "splits.json").read_text())
    split_of = {q: s for s in SPLITS for q in splits[f"{s}_query_ids"]}
    manifests = [json.loads(line) for line in open(pilot / "catalog_manifests.jsonl")]
    records = [PredictionRecord(**json.loads(line)) for line in open(pilot / "predictions.jsonl")]
    frozen_raw = json.loads((pilot / "thresholds.json").read_text())
    pilot_metrics = json.loads((pilot / "metrics.json").read_text())
    max_risk = cfg.get("thresholds", {}).get("max_risk", 0.1)
    frozen = {m: {k: AbstentionPolicy(v["kind"], v["threshold"]) for k, v in pol.items()} for m, pol in frozen_raw.items()}
    methods = sorted(frozen)
    records_by_split = {s: [r for r in records if split_of.get(r.query_id) == s] for s in SPLITS}

    # ------------------------------------------------------------ 1. review sample
    sampled = stratified_review_sample(requests, per_subset=args.review_per_subset)
    export_review_sample(
        sampled, all_tools_by_id, split_of,
        out / "review" / "single_multi_tool_review_sample.csv",
        out / "review" / "single_multi_tool_review_labels_long.csv",
    )
    sample_summary: dict[str, dict[str, int]] = {}
    for s in sampled:
        sample_summary.setdefault(s.stratum, {"population": s.stratum_population, "sampled": 0})["sampled"] += 1

    # ------------------------------------------------------------ 2. catalogs
    held_out_ids = {t.tool_id for t in held_out_tools}
    cat = audit_catalogs(manifests, requests_by_id, all_tools_by_id, held_out_ids)
    cat["methods_identical_inputs"] = audit_methods_saw_identical_inputs(records, manifests)
    cat["distractor_top1_breakdown_by_split"] = {
        s: distractor_selection_breakdown(records_by_split[s], manifests) for s in SPLITS
    }
    # Annotated labels absent from the whole downloaded corpus / from pool.
    all_pilot_reqs = [requests_by_id[q] for q in split_of]
    cat["pilot_requests_with_label_missing_from_corpus"] = sum(
        1 for r in all_pilot_reqs if any(t not in all_tools_by_id for t in r.known_valid_tool_ids)
    )
    cat["subset_tool_families"] = {k: sorted(v) for k, v in subset_families.items()}
    distractor_rows = distractor_top1_review_rows(
        records_by_split["val"] + records_by_split["test"], manifests, requests_by_id, all_tools_by_id, split_of
    )
    write_csv(out / "review" / "distractor_top1_review.csv", distractor_rows)
    cat["n_distractor_top1_review_rows_val_test"] = len(distractor_rows)
    (out / "catalog_audit.json").write_text(json.dumps(cat, indent=2, default=str))
    write_csv(out / "catalog_sizes.csv", cat["catalog_sizes"])

    # ------------------------------------------------------------ 3/4. thresholds
    global_rows = diagnostics_table(
        records_by_split, frozen, max_risk,
        threshold_scope="global per method: one threshold selected on val with all three scenarios pooled",
    )
    write_csv(out / "threshold_diagnostics_frozen_global_policy.csv", global_rows)

    explanations = {}
    traces = {}
    for m in methods:
        val = [r for r in records_by_split["val"] if r.method == m]
        test = [r for r in records_by_split["test"] if r.method == m]
        for kind in (SCORE_THRESHOLD, MARGIN_THRESHOLD):
            explanations[f"{m}::{kind}"] = explain_threshold(val, test, kind, frozen[m][kind].threshold, max_risk)
            tr = selection_trace(val, kind, max_risk)
            traces[f"{m} {kind}"] = tr
            write_csv(out / "val_selection_traces" / f"{m}__{kind}.csv",
                      [{**t, "threshold": t["threshold"]} for t in tr])
            # Per-scenario breakdown at the frozen global threshold (val).
            explanations[f"{m}::{kind}"]["val_counts_by_scenario_at_frozen_threshold"] = {
                row["scenario"]: {k: row[k] for k in ("n_queries", "n_accepted", "n_correct_accepted", "n_incorrect_accepted")}
                for row in global_rows
                if row["method"] == m and row["policy"] == kind and row["split"] == "val"
            }
        plot_signal_distributions(
            {"val": records_by_split["val"], "test": records_by_split["test"]}, m,
            {"score": frozen[m][SCORE_THRESHOLD].threshold, "margin": frozen[m][MARGIN_THRESHOLD].threshold},
            out / "plots" / f"score_margin_distributions_{m}.png",
        )
    plot_val_selection_trace(traces, max_risk, out / "plots" / "val_selection_traces.png")
    (out / "threshold_explanations.json").write_text(json.dumps(explanations, indent=2, default=str))

    # Scenario-specific thresholds: DIAGNOSTIC ONLY (not deployable).
    diag_rows = []
    for m in methods:
        val = [r for r in records_by_split["val"] if r.method == m]
        for kind in (SCORE_THRESHOLD, MARGIN_THRESHOLD):
            for scen, pol in scenario_specific_policies(val, kind, max_risk).items():
                rows = diagnostics_table(
                    {s: [r for r in records_by_split[s] if r.scenario == scen] for s in ("val", "test")},
                    {m: {kind: pol}}, max_risk,
                    threshold_scope=f"DIAGNOSTIC: selected on val '{scen}' rows only",
                )
                diag_rows += [r for r in rows if r["scenario"] == scen]
    write_csv(out / "threshold_diagnostics_scenario_specific_DIAGNOSTIC_ONLY.csv", diag_rows)

    # Paired comparisons (query-grouped bootstrap), always_top1 label agreement.
    paired = {}
    for split in ("val", "test"):
        recs = records_by_split[split]
        for m in methods:
            by_s = {s: [r for r in recs if r.method == m and r.scenario == s] for s in (ORIGINAL, DISTRACTORS_ADDED, KNOWN_REMOVED)}
            paired[f"{split}::{m}::original_minus_distractors_added"] = paired_accuracy_difference(
                by_s[ORIGINAL], by_s[DISTRACTORS_ADDED], seed=0)
        for s in (ORIGINAL, DISTRACTORS_ADDED):
            a = [r for r in recs if r.method == "bm25" and r.scenario == s]
            b = [r for r in recs if r.method == "embedding" and r.scenario == s]
            paired[f"{split}::{s}::bm25_minus_embedding"] = paired_accuracy_difference(a, b, seed=0)
    (out / "paired_comparisons.json").write_text(json.dumps(paired, indent=2))

    # ------------------------------------------------------------ 5. bounded review set
    pool_fn = _toolret_pool_fn_factory(tools_by_id, subset_families)
    items = build_bounded_review_set(
        requests, set(split_of), pool_fn, tools_by_id, per_subset=args.bounded_per_subset
    )
    bounded_paths = export_bounded_review_set(items, tools_by_id, out / "review")

    # ------------------------------------------------------------ reserved confirmatory pool
    # Requests never used by the pilot (dev/val/test) nor shown in any
    # review sheet, minus anything that is an exact/near duplicate of a
    # pilot query. Not evaluated here; this only freezes the ID list.
    shown = set(split_of) | {s.request.query_id for s in sampled} | {it["request"].query_id for it in items}
    pilot_keys = {normalize_for_grouping(requests_by_id[q].query_text) for q in split_of}
    pilot_toks = [_tokens(requests_by_id[q].query_text) for q in split_of]
    reserved, dropped_near_dup = [], 0
    for r in requests:
        if r.query_id in shown:
            continue
        t = _tokens(r.query_text)
        if normalize_for_grouping(r.query_text) in pilot_keys or any(jaccard(t, p) >= 0.8 for p in pilot_toks):
            dropped_near_dup += 1
            continue
        reserved.append(r)
    reserved_by_subset: dict[str, int] = {}
    for r in reserved:
        reserved_by_subset[r.raw["subset"]] = reserved_by_subset.get(r.raw["subset"], 0) + 1
    (out / "reserved_confirmatory_query_ids.json").write_text(json.dumps({
        "purpose": "Fresh held-out pool for a future confirmatory evaluation. Do not evaluate, inspect "
                   "predictions on, or tune against these queries until the final protocol is frozen.",
        "excluded": "pilot dev/val/test queries, all review-sheet queries, and exact/near-duplicates "
                    "(normalized text or token Jaccard >= 0.8) of pilot queries",
        "caveat": "Same five source subsets and tool families as the pilot: this is NOT an unseen-family split.",
        "n_reserved": len(reserved),
        "n_dropped_as_near_duplicate_of_pilot": dropped_near_dup,
        "n_by_subset": dict(sorted(reserved_by_subset.items())),
        "query_ids": sorted(r.query_id for r in reserved),
    }, indent=2))

    # ------------------------------------------------------------ 6. leakage / repro
    leak = leakage_report(requests, split_of, all_tools_by_id)
    (out / "leakage.json").write_text(json.dumps(leak, indent=2))

    emb_cfg = cfg.get("embedding", {})
    metas = sorted(Path(emb_cfg.get("cache_dir", "data/cache/embeddings")).rglob("*.meta.json"))
    repro = {
        "data_manifest": {k: v for k, v in json.loads(Path(cfg["toolret"]["raw_dir"], "manifest.json").read_text()).items() if k != "files"},
        "configured_embedding_revision": emb_cfg.get("revision"),
        "configured_revision_is_immutable_sha": is_immutable_revision(emb_cfg.get("revision")),
        "embedding_cache_metadata": [{"path": str(p), **json.loads(p.read_text())} for p in metas],
        "pilot_run_config_embedding": json.loads((pilot / "run_metadata.json").read_text())["config"].get("embedding"),
        "pilot_git_commit": json.loads((pilot / "run_metadata.json").read_text()).get("git_commit"),
        "pilot_artifact_sha256": hashes_before,
    }
    (out / "reproducibility.json").write_text(json.dumps(repro, indent=2))

    # ------------------------------------------------------------ summary md
    lines = ["# Evaluation audit -- generated tables", "",
             f"Source run: `{pilot}` (read-only). Labels are known-incomplete; 'correct' = top-1 in annotated labels.", ""]
    for split in SPLITS:
        lines += [f"## Frozen global policy, split = {split}", ""] + md_counts_table(global_rows, split) + [""]
    lines += ["## Scenario-specific thresholds (DIAGNOSTIC ONLY, not deployable)", ""]
    for split in ("val", "test"):
        lines += [f"### split = {split}", ""] + md_counts_table(diag_rows, split) + [""]
    lines += ["## Paired comparisons (always_top1 label agreement, query-grouped bootstrap, 2000 resamples)", "",
              "| comparison | n paired | A correct | B correct | A-only | B-only | diff | 95% CI |", "|---|---|---|---|---|---|---|---|"]
    for k, d in paired.items():
        lines.append(f"| {k} | {d['n_paired_queries']} | {d['a_correct']} | {d['b_correct']} | {d['a_only_correct']} | "
                     f"{d['b_only_correct']} | {d['diff']:+.3f} | [{d['ci95_low']:+.3f}, {d['ci95_high']:+.3f}] |")
    lines += ["", "## Catalog checks", "", "| check | checked | violations |", "|---|---|---|"]
    for c in cat["checks"]:
        lines.append(f"| {c['check']} | {c['n_checked']} | {c['n_violations']} |")
    lines += ["", "## Catalog sizes", "", "| subset | scenario | n | min | median | mean | max |", "|---|---|---|---|---|---|---|"]
    for r in cat["catalog_sizes"]:
        lines.append(f"| {r['subset']} | {r['scenario']} | {r['n_catalogs']} | {r['min']} | {r['median']} | {r['mean']} | {r['max']} |")
    lines += ["", "## Review sample strata", "", "| stratum | population | sampled |", "|---|---|---|"]
    for k, v in sorted(sample_summary.items()):
        lines.append(f"| {k} | {v['population']} | {v['sampled']} |")
    lines += ["", f"Bounded-catalog review items: {len(items)} -> {bounded_paths}", ""]
    lines += ["## Pilot REPORT.md cross-check (test, always_top1)", ""]
    for m in methods:
        for s in (ORIGINAL, DISTRACTORS_ADDED, KNOWN_REMOVED):
            pm = pilot_metrics.get(f"{m}::{s}::{ALWAYS_TOP1}", {})
            mine = [r for r in global_rows if r["method"] == m and r["scenario"] == s and r["split"] == "test" and r["policy"] == ALWAYS_TOP1][0]
            lines.append(f"- {m}/{s}: pilot top1_accuracy={pm.get('top1_accuracy')} vs audit "
                         f"{mine['n_correct_accepted']}/{mine['n_accepted']}")
    (out / "audit_tables.md").write_text("\n".join(lines) + "\n")

    hashes_after = hash_dir(pilot)
    if hashes_after != hashes_before:
        sys.exit("ERROR: pilot directory changed during audit")
    print(f"Pilot outputs unchanged ({len(hashes_before)} files hash-verified). Audit written to {out}/")


if __name__ == "__main__":
    main()
