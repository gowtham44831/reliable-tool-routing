"""Checks on catalog-scenario construction (original / known_removed /
distractors_added) and on whether compared methods saw identical inputs.

All checks return plain counts plus a small list of example violations so
the audit document can show numerators and denominators.
"""
from __future__ import annotations

import hashlib
import statistics
from collections import defaultdict

from tool_routing.data.schema import Request, Tool
from tool_routing.evaluation.records import PredictionRecord
from tool_routing.scenarios.catalog import DISTRACTORS_ADDED, KNOWN_REMOVED, ORIGINAL

MAX_EXAMPLES = 5


def _content_fingerprint(tool: Tool) -> str:
    """Whitespace/case-normalized name+description+parameters hash, used to
    detect distinct IDs that carry the same content."""
    text = " ".join(tool.serialized_text().lower().split())
    return hashlib.sha256(text.encode()).hexdigest()


def _subset_of(request: Request) -> str:
    return request.raw.get("subset", request.source_dataset)


class _Check:
    def __init__(self, name: str):
        self.name = name
        self.n_checked = 0
        self.n_violations = 0
        self.examples: list[str] = []

    def record(self, ok: bool, example: str = "") -> None:
        self.n_checked += 1
        if not ok:
            self.n_violations += 1
            if len(self.examples) < MAX_EXAMPLES:
                self.examples.append(example)

    def to_dict(self) -> dict:
        return {
            "check": self.name,
            "n_checked": self.n_checked,
            "n_violations": self.n_violations,
            "passed": self.n_violations == 0,
            "examples": self.examples,
        }


def audit_catalogs(
    manifests: list[dict],
    requests_by_id: dict[str, Request],
    all_tools_by_id: dict[str, Tool],
    held_out_ids: set[str],
) -> dict:
    """Verify scenario construction invariants on serialized manifests.

    ``manifests`` are dicts as written to ``catalog_manifests.jsonl``.
    """
    by_query: dict[str, dict[str, dict]] = defaultdict(dict)
    for m in manifests:
        by_query[m["query_id"]][m["scenario"]] = m

    checks = {
        name: _Check(name)
        for name in (
            "all_three_scenarios_present",
            "original_contains_every_annotated_tool",
            "known_removed_equals_original_minus_annotated",
            "known_removed_contains_no_annotated_tool",
            "distractors_not_in_original_by_id",
            "distractors_from_held_out_pool",
            "distractors_resolve_to_known_tools",
            "distractors_unique_within_catalog",
            "distractors_added_equals_original_plus_distractors",
            "distractors_content_distinct_from_original",
            "distractors_not_annotated_valid",
            "catalog_tool_ids_unique",
        )
    }
    annotated_missing_from_original: dict[str, int] = defaultdict(int)
    fingerprint_cache: dict[str, str] = {}

    def fp(tid: str) -> str | None:
        if tid not in fingerprint_cache:
            tool = all_tools_by_id.get(tid)
            fingerprint_cache[tid] = _content_fingerprint(tool) if tool else None
        return fingerprint_cache[tid]

    original_fp_sets: dict[tuple[str, ...], set[str]] = {}
    sizes: dict[tuple[str, str], list[int]] = defaultdict(list)
    n_distractors_hist: dict[int, int] = defaultdict(int)
    duplicate_content_in_original: dict[str, int] = {}

    for qid, scen in sorted(by_query.items()):
        req = requests_by_id.get(qid)
        checks["all_three_scenarios_present"].record(
            set(scen) == {ORIGINAL, KNOWN_REMOVED, DISTRACTORS_ADDED}, qid
        )
        if req is None or ORIGINAL not in scen:
            continue
        subset = _subset_of(req)
        orig = scen[ORIGINAL]["tool_ids"]
        orig_set = set(orig)
        valid = set(req.known_valid_tool_ids)

        for name, m in scen.items():
            sizes[(subset, name)].append(len(m["tool_ids"]))
            checks["catalog_tool_ids_unique"].record(
                len(m["tool_ids"]) == len(set(m["tool_ids"])), m["catalog_id"]
            )

        missing = valid - orig_set
        checks["original_contains_every_annotated_tool"].record(
            not missing, f"{qid}: missing {sorted(missing)}"
        )
        if missing:
            annotated_missing_from_original[subset] += 1

        key = tuple(orig)
        if key not in original_fp_sets:
            fps = [fp(t) for t in orig]
            original_fp_sets[key] = set(f for f in fps if f)
            duplicate_content_in_original[f"{subset}:{len(orig)}"] = len(fps) - len(set(fps))

        kr = scen.get(KNOWN_REMOVED)
        if kr is not None:
            kr_set = set(kr["tool_ids"])
            checks["known_removed_equals_original_minus_annotated"].record(
                kr_set == orig_set - valid, qid
            )
            checks["known_removed_contains_no_annotated_tool"].record(
                not (kr_set & valid), f"{qid}: still contains {sorted(kr_set & valid)}"
            )

        da = scen.get(DISTRACTORS_ADDED)
        if da is not None:
            added = list(da["added_distractor_ids"])
            n_distractors_hist[len(added)] += 1
            checks["distractors_not_in_original_by_id"].record(
                not (set(added) & orig_set), f"{qid}: {sorted(set(added) & orig_set)}"
            )
            checks["distractors_from_held_out_pool"].record(
                set(added) <= held_out_ids, f"{qid}: {sorted(set(added) - held_out_ids)}"
            )
            checks["distractors_resolve_to_known_tools"].record(
                all(t in all_tools_by_id for t in added), qid
            )
            checks["distractors_unique_within_catalog"].record(len(added) == len(set(added)), qid)
            checks["distractors_added_equals_original_plus_distractors"].record(
                set(da["tool_ids"]) == orig_set | set(added), qid
            )
            dup_content = [t for t in added if fp(t) in original_fp_sets[key]]
            checks["distractors_content_distinct_from_original"].record(
                not dup_content, f"{qid}: {dup_content}"
            )
            checks["distractors_not_annotated_valid"].record(
                not (set(added) & valid), f"{qid}: {sorted(set(added) & valid)}"
            )

    size_table = []
    for (subset, scenario), vals in sorted(sizes.items()):
        size_table.append(
            {
                "subset": subset,
                "scenario": scenario,
                "n_catalogs": len(vals),
                "min": min(vals),
                "median": statistics.median(vals),
                "mean": round(statistics.fmean(vals), 2),
                "max": max(vals),
            }
        )
    for scenario in (ORIGINAL, KNOWN_REMOVED, DISTRACTORS_ADDED):
        vals = [v for (s, sc), vs in sizes.items() if sc == scenario for v in vs]
        if vals:
            size_table.append(
                {
                    "subset": "ALL",
                    "scenario": scenario,
                    "n_catalogs": len(vals),
                    "min": min(vals),
                    "median": statistics.median(vals),
                    "mean": round(statistics.fmean(vals), 2),
                    "max": max(vals),
                }
            )

    return {
        "n_queries": len(by_query),
        "checks": [c.to_dict() for c in checks.values()],
        "catalog_sizes": size_table,
        "n_distractors_per_catalog_histogram": dict(sorted(n_distractors_hist.items())),
        "queries_with_annotated_tool_missing_from_original_by_subset": dict(annotated_missing_from_original),
        "duplicate_content_ids_within_original_pool": duplicate_content_in_original,
    }


def audit_methods_saw_identical_inputs(
    records: list[PredictionRecord], manifests: list[dict]
) -> dict:
    """Empirical check that every method was run on the same (query,
    scenario) catalogs and that every returned tool ID lies inside the
    manifest's catalog. Catalog *construction* is shared by code design
    (``evaluation/pipeline.py`` builds one tool list per manifest and passes
    it to every retriever); this check guards against drift."""
    catalog_tools = {m["catalog_id"]: set(m["tool_ids"]) for m in manifests}
    by_method: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    out_of_catalog = _Check("returned_tool_ids_inside_catalog")
    for r in records:
        by_method[r.method].add((r.query_id, r.scenario, r.catalog_id))
        allowed = catalog_tools.get(r.catalog_id, set())
        bad = [t for t in r.top_k_tool_ids if t not in allowed]
        out_of_catalog.record(not bad, f"{r.method} {r.catalog_id}: {bad[:3]}")
    methods = sorted(by_method)
    keysets = [by_method[m] for m in methods]
    identical = all(k == keysets[0] for k in keysets) if keysets else True
    return {
        "methods": methods,
        "n_query_scenario_pairs_per_method": {m: len(by_method[m]) for m in methods},
        "identical_query_scenario_catalog_sets": identical,
        "returned_ids_check": out_of_catalog.to_dict(),
    }


DISTRACTOR_REVIEW_FIELDS = [
    "review_id",
    "query_id",
    "split",
    "methods_with_this_top1",
    "query_text",
    "annotated_tools_detail",
    "distractor_tool_id",
    "distractor_family",
    "distractor_name",
    "distractor_description",
    "judgment_distractor_satisfies_request",  # yes | no | unclear
    "reviewer_id",
    "reviewer_notes",
    "human_reviewed",
]


def distractor_top1_review_rows(
    records: list[PredictionRecord],
    manifests: list[dict],
    requests_by_id: dict[str, Request],
    tools_by_id: dict[str, Tool],
    split_of: dict[str, str],
) -> list[dict]:
    """One row per (query, added distractor) that some method ranked top-1.

    These are currently scored as errors only because the distractor is
    not in the annotated label set; a human must judge whether the added
    tool actually satisfies the request. Judgment columns are blank.
    """
    added = {
        m["catalog_id"]: set(m["added_distractor_ids"]) for m in manifests if m["scenario"] == DISTRACTORS_ADDED
    }
    picks: dict[tuple[str, str], set[str]] = defaultdict(set)
    for r in records:
        if r.scenario == DISTRACTORS_ADDED and r.top_k_tool_ids and r.top_k_tool_ids[0] in added.get(r.catalog_id, ()):
            picks[(r.query_id, r.top_k_tool_ids[0])].add(r.method)
    rows = []
    for i, ((qid, tid), methods) in enumerate(sorted(picks.items()), start=1):
        req = requests_by_id[qid]
        tool = tools_by_id.get(tid)
        rows.append(
            {
                "review_id": f"DR{i:03d}",
                "query_id": qid,
                "split": split_of.get(qid, ""),
                "methods_with_this_top1": "; ".join(sorted(methods)),
                "query_text": req.query_text,
                "annotated_tools_detail": "\n".join(
                    f"{t} :: {tools_by_id[t].name} :: {' '.join(tools_by_id[t].description.split())[:400]}"
                    if t in tools_by_id
                    else f"{t} :: [not found]"
                    for t in req.known_valid_tool_ids
                ),
                "distractor_tool_id": tid,
                "distractor_family": tool.tool_family if tool else "",
                "distractor_name": tool.name if tool else "",
                "distractor_description": tool.description if tool else "",
                **{k: "" for k in DISTRACTOR_REVIEW_FIELDS[10:]},
            }
        )
    return rows


def distractor_selection_breakdown(
    records: list[PredictionRecord], manifests: list[dict]
) -> list[dict]:
    """How often top-1 lands on an added distractor in distractors_added.

    The metrics code scores any top-1 outside ``known_valid_tool_ids`` as
    'incorrect', so a top-1 distractor is counted as an error even though no
    one has checked that the distractor is actually irrelevant. This breaks
    those 'errors' out so they are not silently treated as confirmed.
    """
    added = {
        m["catalog_id"]: set(m["added_distractor_ids"])
        for m in manifests
        if m["scenario"] == DISTRACTORS_ADDED
    }
    rows: dict[str, dict] = {}
    for r in records:
        if r.scenario != DISTRACTORS_ADDED or not r.top_k_tool_ids:
            continue
        row = rows.setdefault(
            r.method,
            {"method": r.method, "n": 0, "top1_label_match": 0, "top1_added_distractor": 0, "top1_other_unlabeled": 0},
        )
        row["n"] += 1
        top1 = r.top_k_tool_ids[0]
        if top1 in r.known_valid_tool_ids:
            row["top1_label_match"] += 1
        elif top1 in added.get(r.catalog_id, set()):
            row["top1_added_distractor"] += 1
        else:
            row["top1_other_unlabeled"] += 1
    return [rows[m] for m in sorted(rows)]
