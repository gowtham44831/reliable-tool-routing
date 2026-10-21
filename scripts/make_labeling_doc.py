"""Emit a blind Markdown labeling doc + blank responses CSV for bounded-
catalog review items.

    python scripts/make_labeling_doc.py --round 1            # items 1-10
    python scripts/make_labeling_doc.py --round 2            # items 11-40

Reads only the blind review CSVs (items/tools) plus the tool corpus for
full descriptions. Never reads the answer key, never emits labels,
scores, rankings, or scenario names.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from tool_routing.audit.labeling_doc import (
    export_response_template,
    load_items_and_catalogs,
    render_labeling_doc,
)
from tool_routing.data.toolret_adapter import load_toolret_tools

ROUNDS = {1: (0, 10), 2: (10, 40)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/pilot_toolret.yaml")
    ap.add_argument("--review-dir", default="results/evaluation_audit/review")
    ap.add_argument("--out-dir", default="results/evaluation_audit/human_labeling")
    ap.add_argument("--round", type=int, required=True, choices=sorted(ROUNDS))
    args = ap.parse_args()

    items, _ = load_items_and_catalogs(args.review_dir)
    lo, hi = ROUNDS[args.round]
    batch = items[lo:hi]

    cfg = yaml.safe_load(Path(args.config).read_text())
    all_tools = load_toolret_tools(cfg["toolret"]["raw_dir"])

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    exposure = (
        "the reviewer has already seen a compact summary of these items "
        "(request text + tool names) in the session transcript. This "
        "round is therefore not fully blind -- keep results exploratory."
        if args.round == 1 else None
    )
    md = out / f"bounded_labeling_round{args.round}.md"
    md.write_text(
        render_labeling_doc(
            batch, all_tools,
            title=f"Bounded-catalog labeling — round {args.round}",
            exposure_note=exposure,
        )
    )
    resp = out / "responses" / f"bounded_round{args.round}_responses.csv"
    export_response_template(batch, resp)
    ids = [i.item_id for i in batch]
    print(f"Wrote {md} ({len(batch)} items: {ids[0]}..{ids[-1]})")
    print(f"Blank responses template: {resp}")


if __name__ == "__main__":
    main()
