"""Deterministic pilot split construction (dev/val/test).

Duplicate and near-duplicate queries are grouped (by normalized text) and
kept together in a single split, so paraphrase-only variants of the same
underlying request cannot leak across dev/val/test.

Tool-family leakage avoidance: we additionally record, per split, which
tool families are referenced by its queries, and report any families that
appear in more than one split. We do NOT attempt to force disjoint tool
families across splits, because family labels are a best-effort heuristic
(see Tool.tool_family / docs/dataset.md) and are not independently
verified. Any claim of "generalizing to unseen tools" based on this split
alone would be unsupported -- see docs/dataset.md limitations.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

from tool_routing.data.schema import Request, Tool

_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]")


def normalize_for_grouping(text: str) -> str:
    t = text.strip().lower()
    t = _PUNCT_RE.sub("", t)
    t = _WS_RE.sub(" ", t)
    return t.strip()


@dataclass
class SplitManifest:
    seed: int
    dev_query_ids: list[str] = field(default_factory=list)
    val_query_ids: list[str] = field(default_factory=list)
    test_query_ids: list[str] = field(default_factory=list)
    groups: dict[str, list[str]] = field(default_factory=dict)  # group_key -> query_ids
    group_split: dict[str, str] = field(default_factory=dict)  # group_key -> split name
    family_overlap_warnings: list[str] = field(default_factory=list)
    n_total_queries: int = 0
    n_available_queries: int = 0

    def split_of(self, query_id: str) -> str | None:
        for split_name, ids in (
            ("dev", self.dev_query_ids),
            ("val", self.val_query_ids),
            ("test", self.test_query_ids),
        ):
            if query_id in ids:
                return split_name
        return None

    def to_dict(self) -> dict:
        return {
            "seed": self.seed,
            "n_total_queries": self.n_total_queries,
            "n_available_queries": self.n_available_queries,
            "n_dev": len(self.dev_query_ids),
            "n_val": len(self.val_query_ids),
            "n_test": len(self.test_query_ids),
            "dev_query_ids": self.dev_query_ids,
            "val_query_ids": self.val_query_ids,
            "test_query_ids": self.test_query_ids,
            "groups": self.groups,
            "group_split": self.group_split,
            "family_overlap_warnings": self.family_overlap_warnings,
        }


def make_pilot_splits(
    requests: list[Request],
    tools_by_id: dict[str, Tool],
    seed: int = 42,
    max_total: int | None = 500,
    dev_frac: float = 0.6,
    val_frac: float = 0.2,
) -> SplitManifest:
    """Build deterministic dev/val/test splits grouped by near-duplicate text.

    ``dev_frac``/``val_frac`` control the approximate group-count split;
    the remainder goes to test.
    """
    rng = random.Random(seed)

    groups: dict[str, list[str]] = {}
    for r in requests:
        key = normalize_for_grouping(r.query_text)
        groups.setdefault(key, []).append(r.query_id)

    group_keys = sorted(groups.keys())  # deterministic order before shuffling
    rng.shuffle(group_keys)

    n_total_queries = len(requests)

    if max_total is not None and max_total < n_total_queries:
        selected_keys: list[str] = []
        count = 0
        for key in group_keys:
            if count >= max_total:
                break
            selected_keys.append(key)
            count += len(groups[key])
        group_keys = selected_keys

    n_available = sum(len(groups[k]) for k in group_keys)

    dev_target = dev_frac * n_available
    val_target = (dev_frac + val_frac) * n_available

    manifest = SplitManifest(seed=seed, n_total_queries=n_total_queries, n_available_queries=n_available)
    manifest.groups = {k: groups[k] for k in group_keys}

    running = 0
    for key in group_keys:
        size = len(groups[key])
        if running < dev_target:
            split_name = "dev"
            manifest.dev_query_ids.extend(groups[key])
        elif running < val_target:
            split_name = "val"
            manifest.val_query_ids.extend(groups[key])
        else:
            split_name = "test"
            manifest.test_query_ids.extend(groups[key])
        manifest.group_split[key] = split_name
        running += size

    # Diagnostic (not enforced): tool families referenced in more than one
    # split.
    requests_by_id = {r.query_id: r for r in requests}
    family_by_split: dict[str, set[str]] = {"dev": set(), "val": set(), "test": set()}
    for split_name, ids in (
        ("dev", manifest.dev_query_ids),
        ("val", manifest.val_query_ids),
        ("test", manifest.test_query_ids),
    ):
        for qid in ids:
            req = requests_by_id.get(qid)
            if req is None:
                continue
            for tid in req.known_valid_tool_ids:
                tool = tools_by_id.get(tid)
                if tool is not None and tool.tool_family:
                    family_by_split[split_name].add(tool.tool_family)

    overlaps = (
        (family_by_split["dev"] & family_by_split["val"])
        | (family_by_split["dev"] & family_by_split["test"])
        | (family_by_split["val"] & family_by_split["test"])
    )
    if overlaps:
        manifest.family_overlap_warnings = sorted(overlaps)

    return manifest
