"""Split-leakage diagnostics: query variants, shared tools, tool families,
and source datasets across dev/val/test."""
from __future__ import annotations

import re
from collections import defaultdict
from itertools import combinations

from tool_routing.data.schema import Request, Tool
from tool_routing.scenarios.splits import normalize_for_grouping

_TOKEN_RE = re.compile(r"[a-z0-9]+")
SPLITS = ("dev", "val", "test")


def _tokens(text: str) -> frozenset[str]:
    return frozenset(_TOKEN_RE.findall(text.lower()))


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def leakage_report(
    requests: list[Request],
    split_of: dict[str, str],
    tools_by_id: dict[str, Tool],
    near_dup_jaccard: float = 0.8,
    max_examples: int = 10,
) -> dict:
    reqs = [r for r in requests if r.query_id in split_of]

    # 1. Exact (normalized-text) variant groups must sit in one split.
    groups: dict[str, set[str]] = defaultdict(set)
    group_sizes: dict[str, int] = defaultdict(int)
    for r in reqs:
        key = normalize_for_grouping(r.query_text)
        groups[key].add(split_of[r.query_id])
        group_sizes[key] += 1
    split_violations = [k for k, s in groups.items() if len(s) > 1]
    n_multi_member_groups = sum(1 for k, n in group_sizes.items() if n > 1)

    # 2. Near-duplicate (token Jaccard) pairs across different splits --
    # catches paraphrase/template variants that exact normalization misses.
    toks = {r.query_id: _tokens(r.query_text) for r in reqs}
    cross_pairs = []
    n_pairs_by_splits: dict[str, int] = defaultdict(int)
    for a, b in combinations(reqs, 2):
        sa, sb = split_of[a.query_id], split_of[b.query_id]
        if sa == sb:
            continue
        j = jaccard(toks[a.query_id], toks[b.query_id])
        if j >= near_dup_jaccard:
            key = "-".join(sorted((sa, sb)))
            n_pairs_by_splits[key] += 1
            if len(cross_pairs) < max_examples:
                cross_pairs.append(
                    {"a": a.query_id, "b": b.query_id, "splits": key, "jaccard": round(j, 3),
                     "a_text": a.query_text[:160], "b_text": b.query_text[:160]}
                )

    # 3. Annotated tools shared across splits, and identical label sets.
    tools_by_split: dict[str, set[str]] = {s: set() for s in SPLITS}
    labelsets_by_split: dict[str, set[frozenset[str]]] = {s: set() for s in SPLITS}
    fam_by_split: dict[str, set[str]] = {s: set() for s in SPLITS}
    source_counts: dict[str, dict[str, int]] = {s: defaultdict(int) for s in SPLITS}
    for r in reqs:
        s = split_of[r.query_id]
        tools_by_split[s] |= set(r.known_valid_tool_ids)
        labelsets_by_split[s].add(frozenset(r.known_valid_tool_ids))
        source_counts[s][r.raw.get("subset", r.source_dataset)] += 1
        for t in r.known_valid_tool_ids:
            tool = tools_by_id.get(t)
            if tool is not None and tool.tool_family:
                fam_by_split[s].add(tool.tool_family)

    def eval_overlap(target: str) -> dict:
        seen_tools = tools_by_split["dev"] | (tools_by_split["val"] if target == "test" else set())
        seen_labelsets = labelsets_by_split["dev"] | (labelsets_by_split["val"] if target == "test" else set())
        target_reqs = [r for r in reqs if split_of[r.query_id] == target]
        return {
            "n_queries": len(target_reqs),
            "n_with_any_annotated_tool_seen_in_earlier_splits": sum(
                1 for r in target_reqs if set(r.known_valid_tool_ids) & seen_tools
            ),
            "n_with_identical_label_set_in_earlier_splits": sum(
                1 for r in target_reqs if frozenset(r.known_valid_tool_ids) in seen_labelsets
            ),
            "n_distinct_annotated_tools": len(tools_by_split[target]),
            "n_distinct_annotated_tools_also_in_earlier_splits": len(tools_by_split[target] & seen_tools),
        }

    families_all = sorted(set().union(*fam_by_split.values()))
    return {
        "exact_variant_groups": {
            "n_groups": len(groups),
            "n_groups_with_more_than_one_query": n_multi_member_groups,
            "n_groups_spanning_multiple_splits": len(split_violations),
            "examples": split_violations[:max_examples],
        },
        "near_duplicate_cross_split_pairs": {
            "jaccard_threshold": near_dup_jaccard,
            "n_pairs_by_split_pair": dict(n_pairs_by_splits),
            "examples": cross_pairs,
        },
        "annotated_tool_overlap": {"val_vs_dev": eval_overlap("val"), "test_vs_dev_val": eval_overlap("test")},
        "tool_families_by_split": {s: sorted(fam_by_split[s]) for s in SPLITS},
        "tool_families_in_all_three_splits": sorted(
            f for f in families_all if all(f in fam_by_split[s] for s in SPLITS)
        ),
        "source_subset_counts_by_split": {s: dict(sorted(source_counts[s].items())) for s in SPLITS},
    }
