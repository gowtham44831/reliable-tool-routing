"""Small, bounded-catalog answerability review set.

Purpose: get a set of (request, catalog) items where a human can inspect
EVERY tool in the catalog and judge whether ANY tool satisfies the
request. Only a judgment over the whole catalog can establish true
(un)answerability; the full-corpus/reduced-catalog benchmark cannot.

Design:

* Requests are drawn only from queries NOT used in the pilot dev/val/test
  splits, so this set stays separate from (and cannot be tuned against)
  the existing exploratory benchmark.
* Each catalog has at most ``max_catalog_size`` tools: lexically similar
  tools from the request's own source-subset pool (BM25, so the judgment
  is non-trivial) plus a few random tools from the same pool.
* Half of the items keep the annotated tools in the catalog, half remove
  them. Which condition an item is in is written ONLY to a separate key
  file so reviewers can judge blind. The condition is NOT a label: a
  'removed' item may still be answerable via another tool, and a 'kept'
  item may still be judged unanswerable if the annotation is wrong.
* All judgment columns are blank; nothing is marked reviewed.

Construction uses BM25 over tool text, so a later BM25 evaluation on this
set is not independent of how the catalogs were assembled; this is
documented in docs/evaluation_audit.md.
"""
from __future__ import annotations

import csv
import json
import random
from pathlib import Path

from tool_routing.data.schema import Request, Tool
from tool_routing.retrieval.bm25 import BM25Retriever

KEEP = "annotated_tools_kept"
REMOVE = "annotated_tools_removed"

ITEM_FIELDS = [
    "item_id",
    "query_text",
    "n_tools_in_catalog",
    "judgment_any_tool_satisfies",  # yes | no | unclear
    "judgment_satisfying_tool_ids",  # '; '-separated tool_ids from this item's catalog
    "judgment_request_type",  # single-tool | multi-tool | unclear
    "reviewer_id",
    "reviewer_notes",
    "human_reviewed",  # reviewer sets 'yes' only after inspecting every tool
]
TOOL_FIELDS = ["item_id", "slot", "tool_id", "tool_name", "tool_description", "tool_parameters"]
KEY_FIELDS = ["item_id", "query_id", "source_subset", "condition", "annotated_tool_ids", "annotated_ids_in_catalog"]


def build_bounded_review_set(
    requests: list[Request],
    excluded_query_ids: set[str],
    pool_fn,
    tools_by_id: dict[str, Tool],
    per_subset: int = 8,
    max_catalog_size: int = 15,
    n_random: int = 4,
    seed: int = 7,
) -> list[dict]:
    rng = random.Random(seed)
    by_subset: dict[str, list[Request]] = {}
    for r in requests:
        if r.query_id in excluded_query_ids or not r.known_valid_tool_ids:
            continue
        by_subset.setdefault(r.raw.get("subset", r.source_dataset), []).append(r)

    items = []
    retrievers: dict[tuple[str, ...], tuple[BM25Retriever, str]] = {}
    for subset in sorted(by_subset):
        members = sorted(by_subset[subset], key=lambda r: r.query_id)
        chosen = rng.sample(members, min(per_subset, len(members)))
        for i, r in enumerate(chosen):
            condition = KEEP if i % 2 == 0 else REMOVE
            pool = sorted({t for t in pool_fn(r) if t in tools_by_id})
            valid = [t for t in r.known_valid_tool_ids if t in tools_by_id]
            key = tuple(pool)
            if key not in retrievers:
                ret = BM25Retriever()
                cid = f"bounded::{subset}::{len(pool)}"
                ret.prepare_catalog(cid, [tools_by_id[t] for t in pool])
                retrievers[key] = (ret, cid)
            ret, cid = retrievers[key]
            ranked = ret.rank(cid, r.query_text, top_k=max_catalog_size + len(valid) + 5).tool_ids
            non_valid_ranked = [t for t in ranked if t not in valid]

            keep_valid = valid[: max(1, max_catalog_size // 3)] if condition == KEEP else []
            n_similar = max(0, max_catalog_size - len(keep_valid) - n_random)
            catalog = list(keep_valid) + non_valid_ranked[:n_similar]
            remaining = [t for t in pool if t not in catalog and t not in valid]
            catalog += rng.sample(remaining, min(max_catalog_size - len(catalog), len(remaining)))
            rng.shuffle(catalog)
            items.append(
                {
                    "request": r,
                    "subset": subset,
                    "condition": condition,
                    "catalog": catalog,
                    "annotated_in_catalog": [t for t in catalog if t in set(r.known_valid_tool_ids)],
                }
            )
    rng.shuffle(items)
    for n, it in enumerate(items, start=1):
        it["item_id"] = f"BC{n:03d}"
    return items


def export_bounded_review_set(items: list[dict], tools_by_id: dict[str, Tool], out_dir: str | Path) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "items": out_dir / "bounded_catalog_review_items.csv",
        "tools": out_dir / "bounded_catalog_review_tools.csv",
        "key": out_dir / "bounded_catalog_review_KEY_do_not_open_before_review.csv",
    }
    with open(paths["items"], "w", newline="", encoding="utf-8") as fi, open(
        paths["tools"], "w", newline="", encoding="utf-8"
    ) as ft, open(paths["key"], "w", newline="", encoding="utf-8") as fk:
        wi = csv.DictWriter(fi, fieldnames=ITEM_FIELDS)
        wt = csv.DictWriter(ft, fieldnames=TOOL_FIELDS)
        wk = csv.DictWriter(fk, fieldnames=KEY_FIELDS)
        for w in (wi, wt, wk):
            w.writeheader()
        for it in sorted(items, key=lambda x: x["item_id"]):
            r = it["request"]
            wi.writerow(
                {"item_id": it["item_id"], "query_text": r.query_text, "n_tools_in_catalog": len(it["catalog"]),
                 **{k: "" for k in ITEM_FIELDS[3:]}}
            )
            for slot, tid in enumerate(it["catalog"], start=1):
                t = tools_by_id[tid]
                wt.writerow(
                    {"item_id": it["item_id"], "slot": slot, "tool_id": tid, "tool_name": t.name,
                     "tool_description": t.description,
                     "tool_parameters": json.dumps(t.parameters, sort_keys=True, ensure_ascii=False, default=str)}
                )
            wk.writerow(
                {"item_id": it["item_id"], "query_id": r.query_id, "source_subset": it["subset"],
                 "condition": it["condition"], "annotated_tool_ids": "; ".join(r.known_valid_tool_ids),
                 "annotated_ids_in_catalog": "; ".join(it["annotated_in_catalog"])}
            )
    return {k: str(v) for k, v in paths.items()}
