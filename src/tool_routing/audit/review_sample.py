"""Stratified human-review sample for single-tool vs. multi-tool eligibility.

The pilot's "single-tool" classification is a *subset-level* heuristic
(``data/toolret_constants.py``). This module draws a deterministic
stratified sample of original requests so that a human can judge, per
request, whether it needs one tool, several jointly-required tools, or
is unclear -- and whether multiple annotated labels are alternatives or
jointly required.

Nothing here infers those judgments: every judgment column is exported
blank and ``human_reviewed`` is left blank (never auto-filled).
"""
from __future__ import annotations

import csv
import json
import random
from dataclasses import dataclass
from pathlib import Path

from tool_routing.data.schema import Request, Tool

SINGLE_LABEL = "1_label"
MULTI_LABEL = "2plus_labels"

# Blank human-judgment columns. Allowed values are documented in
# docs/review_workflow.md; they are intentionally NOT pre-filled.
JUDGMENT_FIELDS = [
    "judgment_request_type",  # single-tool | multi-tool | unclear
    "judgment_label_relation",  # alternatives | jointly_required | mixed | not_applicable_one_label | unclear
    "judgment_labels_complete",  # yes | no | unclear  (are obviously-valid tools missing from labels?)
    "reviewer_id",
    "reviewer_notes",
    "human_reviewed",  # set to "yes" by the reviewer only after completing the row
]

REVIEW_SAMPLE_FIELDS = [
    "review_id",
    "query_id",
    "source_subset",
    "source_category",
    "upstream_query_id",
    "pilot_split",
    "sampling_stratum",
    "stratum_population",
    "stratum_sample_size",
    "sampling_weight",
    "query_text",
    "n_annotated_tools",
    "annotated_tool_ids",
    "annotated_tools_detail",
    *JUDGMENT_FIELDS,
]

LONG_FIELDS = [
    "review_id",
    "query_id",
    "label_index",
    "tool_id",
    "tool_name",
    "tool_description",
    "tool_parameters",
    "tool_found_in_corpus",
]


@dataclass(frozen=True)
class SampledRequest:
    request: Request
    stratum: str
    stratum_population: int
    stratum_sample_size: int

    @property
    def weight(self) -> float:
        return self.stratum_population / self.stratum_sample_size


def label_stratum(request: Request) -> str:
    return SINGLE_LABEL if len(request.known_valid_tool_ids) <= 1 else MULTI_LABEL


def allocate(
    strata_sizes: dict[tuple[str, str], int], per_subset: int
) -> dict[tuple[str, str], int]:
    """Allocate ``per_subset`` draws per subset across its label strata.

    Within a subset, draws are split equally between the 1-label and
    2+-label strata (multi-label requests are where the alternatives vs.
    jointly-required question actually arises, so they are oversampled
    relative to their population share; ``sampling_weight`` corrects for
    this). A stratum smaller than its share donates the remainder to its
    sibling.
    """
    subsets = sorted({s for s, _ in strata_sizes})
    alloc: dict[tuple[str, str], int] = {}
    for subset in subsets:
        keys = [k for k in strata_sizes if k[0] == subset and strata_sizes[k] > 0]
        keys.sort(key=lambda k: k[1])
        total_available = sum(strata_sizes[k] for k in keys)
        target = min(per_subset, total_available)
        share = {k: 0 for k in keys}
        remaining = target
        # Equal split, capped by stratum size; redistribute leftovers.
        while remaining > 0:
            open_keys = [k for k in keys if share[k] < strata_sizes[k]]
            if not open_keys:
                break
            each = max(1, remaining // len(open_keys))
            for k in open_keys:
                if remaining == 0:
                    break
                add = min(each, strata_sizes[k] - share[k], remaining)
                share[k] += add
                remaining -= add
        alloc.update(share)
    return alloc


def stratified_review_sample(
    requests: list[Request], per_subset: int = 20, seed: int = 2026
) -> list[SampledRequest]:
    """Deterministic stratified sample: ``per_subset`` requests from each
    source subset, split across label-count strata (see ``allocate``)."""
    strata: dict[tuple[str, str], list[Request]] = {}
    for r in requests:
        subset = r.raw.get("subset", r.source_dataset)
        strata.setdefault((subset, label_stratum(r)), []).append(r)
    sizes = {k: len(v) for k, v in strata.items()}
    alloc = allocate(sizes, per_subset)

    rng = random.Random(seed)
    sampled: list[SampledRequest] = []
    for key in sorted(strata):
        members = sorted(strata[key], key=lambda r: r.query_id)
        n = alloc.get(key, 0)
        for r in rng.sample(members, n):
            sampled.append(SampledRequest(r, f"{key[0]}|{key[1]}", sizes[key], n))
    sampled.sort(key=lambda s: (s.request.raw.get("subset", ""), s.stratum, s.request.query_id))
    return sampled


def _tool_detail(tool: Tool | None, tid: str, max_desc: int = 600) -> str:
    if tool is None:
        return f"{tid}: [NOT FOUND IN DOWNLOADED CORPUS]"
    desc = " ".join(tool.description.split())
    if len(desc) > max_desc:
        desc = desc[:max_desc] + "..."
    return f"{tid} :: {tool.name} :: {desc}"


def export_review_sample(
    sampled: list[SampledRequest],
    tools_by_id: dict[str, Tool],
    split_of: dict[str, str],
    out_csv: str | Path,
    out_long_csv: str | Path,
) -> None:
    out_csv, out_long_csv = Path(out_csv), Path(out_long_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f, open(
        out_long_csv, "w", newline="", encoding="utf-8"
    ) as g:
        w = csv.DictWriter(f, fieldnames=REVIEW_SAMPLE_FIELDS)
        wl = csv.DictWriter(g, fieldnames=LONG_FIELDS)
        w.writeheader()
        wl.writeheader()
        for i, s in enumerate(sampled, start=1):
            r = s.request
            review_id = f"SR{i:03d}"
            labels = list(r.known_valid_tool_ids)
            w.writerow(
                {
                    "review_id": review_id,
                    "query_id": r.query_id,
                    "source_subset": r.raw.get("subset", ""),
                    "source_category": r.raw.get("category", ""),
                    "upstream_query_id": r.raw.get("id", ""),
                    "pilot_split": split_of.get(r.query_id, "not_in_pilot"),
                    "sampling_stratum": s.stratum,
                    "stratum_population": s.stratum_population,
                    "stratum_sample_size": s.stratum_sample_size,
                    "sampling_weight": f"{s.weight:.4f}",
                    "query_text": r.query_text,
                    "n_annotated_tools": len(labels),
                    "annotated_tool_ids": "; ".join(labels),
                    "annotated_tools_detail": "\n".join(
                        f"[{j}] " + _tool_detail(tools_by_id.get(t), t) for j, t in enumerate(labels, 1)
                    ),
                    **{k: "" for k in JUDGMENT_FIELDS},
                }
            )
            for j, t in enumerate(labels, 1):
                tool = tools_by_id.get(t)
                wl.writerow(
                    {
                        "review_id": review_id,
                        "query_id": r.query_id,
                        "label_index": j,
                        "tool_id": t,
                        "tool_name": tool.name if tool else "",
                        "tool_description": tool.description if tool else "",
                        "tool_parameters": json.dumps(tool.parameters, sort_keys=True, ensure_ascii=False, default=str)
                        if tool
                        else "",
                        "tool_found_in_corpus": "yes" if tool else "no",
                    }
                )
