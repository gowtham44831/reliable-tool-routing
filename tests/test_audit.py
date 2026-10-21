import csv
import math

from tool_routing.audit.catalog_audit import (
    audit_catalogs,
    audit_methods_saw_identical_inputs,
    distractor_selection_breakdown,
    distractor_top1_review_rows,
)
from tool_routing.audit.leakage import leakage_report
from tool_routing.audit.review_sample import (
    JUDGMENT_FIELDS,
    allocate,
    export_review_sample,
    stratified_review_sample,
)
from tool_routing.audit.threshold_diagnostics import (
    ALL_SCENARIOS,
    count_row,
    diagnostics_table,
    explain_threshold,
    paired_accuracy_difference,
    selection_trace,
)
from tool_routing.data.schema import Request, Tool
from tool_routing.evaluation.records import PredictionRecord
from tool_routing.evaluation.thresholds import (
    ALWAYS_TOP1,
    SCORE_THRESHOLD,
    AbstentionPolicy,
    select_threshold,
)
from tool_routing.retrieval.embeddings import (
    _tool_content_key,
    embedding_settings_fingerprint,
    is_immutable_revision,
)


def req(qid, labels, subset="s1", text=None):
    return Request(
        query_id=qid,
        query_text=text or f"query {qid}",
        known_valid_tool_ids=tuple(labels),
        source_dataset=f"toolret_{subset}",
        raw={"subset": subset, "id": qid, "category": "web"},
    )


def tool(tid, desc=None):
    return Tool(tool_id=tid, name=tid, description=desc or f"does {tid}", tool_family=tid.split("_")[0])


def rec(qid, score, margin, correct, scenario="original", method="bm25"):
    return PredictionRecord(
        query_id=qid,
        catalog_id=f"{qid}::{scenario}",
        scenario=scenario,
        method=method,
        top_k_tool_ids=("t1", "t2"),
        top1_score=score,
        margin=margin,
        known_valid_tool_ids=("t1",) if correct else ("zz",),
        answerability_review_status="unreviewed",
    )


# ---------------------------------------------------------------- review sample


def test_allocate_splits_equally_and_redistributes_small_strata():
    alloc = allocate({("a", "1_label"): 50, ("a", "2plus_labels"): 3, ("b", "1_label"): 100}, per_subset=20)
    assert alloc[("a", "2plus_labels")] == 3
    assert alloc[("a", "1_label")] == 17
    assert alloc[("b", "1_label")] == 20


def test_stratified_sample_is_deterministic_and_balanced(tmp_path):
    requests = [req(f"a{i}", ["t1"], "a") for i in range(30)]
    requests += [req(f"m{i}", ["t1", "t2"], "a") for i in range(30)]
    requests += [req(f"b{i}", ["t3"], "b") for i in range(30)]
    s1 = stratified_review_sample(requests, per_subset=10, seed=1)
    s2 = stratified_review_sample(requests, per_subset=10, seed=1)
    assert [s.request.query_id for s in s1] == [s.request.query_id for s in s2]
    assert len(s1) == 20
    assert sum(1 for s in s1 if s.stratum == "a|2plus_labels") == 5
    assert all(math.isclose(s.weight, s.stratum_population / s.stratum_sample_size) for s in s1)

    out, out_long = tmp_path / "r.csv", tmp_path / "rl.csv"
    export_review_sample(s1, {"t1": tool("t1")}, {}, out, out_long)
    rows = list(csv.DictReader(open(out)))
    assert len(rows) == 20
    # Nothing is pre-judged or marked reviewed.
    for row in rows:
        for f in JUDGMENT_FIELDS:
            assert row[f] == ""
    long_rows = list(csv.DictReader(open(out_long)))
    assert any(r["tool_found_in_corpus"] == "no" for r in long_rows)  # t2/t3 absent from corpus


# ---------------------------------------------------------------- catalog audit


def _manifests(qid, orig, removed, added_ids):
    return [
        {"catalog_id": f"{qid}::original", "query_id": qid, "scenario": "original", "tool_ids": orig,
         "added_distractor_ids": [], "removed_known_valid_ids": []},
        {"catalog_id": f"{qid}::known_removed", "query_id": qid, "scenario": "known_removed",
         "tool_ids": removed, "added_distractor_ids": [], "removed_known_valid_ids": []},
        {"catalog_id": f"{qid}::distractors_added", "query_id": qid, "scenario": "distractors_added",
         "tool_ids": sorted(set(orig) | set(added_ids)), "added_distractor_ids": added_ids,
         "removed_known_valid_ids": []},
    ]


def _checks(result):
    return {c["check"]: c for c in result["checks"]}


def test_catalog_audit_passes_on_well_formed_catalogs():
    tools = {t: tool(t) for t in ["p_1", "p_2", "p_3", "h_1"]}
    r = req("q1", ["p_1"])
    out = audit_catalogs(_manifests("q1", ["p_1", "p_2", "p_3"], ["p_2", "p_3"], ["h_1"]), {"q1": r}, tools, {"h_1"})
    assert all(c["passed"] for c in out["checks"]), out["checks"]
    sizes = {(row["subset"], row["scenario"]): row for row in out["catalog_sizes"]}
    assert sizes[("s1", "original")]["max"] == 3
    assert sizes[("s1", "distractors_added")]["max"] == 4


def test_catalog_audit_flags_missing_annotation_leftover_label_and_duplicate_content():
    tools = {t: tool(t) for t in ["p_1", "p_2", "h_1"]}
    tools["h_2"] = Tool(tool_id="h_2", name="p_2", description="does p_2", tool_family="h")  # same content as p_2
    r = req("q1", ["p_1", "p_9"])  # p_9 is annotated but not in the original catalog
    out = _checks(
        audit_catalogs(_manifests("q1", ["p_1", "p_2"], ["p_1", "p_2"], ["h_2"]), {"q1": r}, tools, {"h_1", "h_2"})
    )
    assert out["original_contains_every_annotated_tool"]["n_violations"] == 1
    assert out["known_removed_contains_no_annotated_tool"]["n_violations"] == 1
    assert out["distractors_content_distinct_from_original"]["n_violations"] == 1


def test_identical_inputs_and_distractor_breakdown():
    manifests = _manifests("q1", ["t1", "t2"], ["t2"], ["d1"])
    recs = [
        PredictionRecord("q1", "q1::distractors_added", "distractors_added", "bm25", ("d1", "t1"), 1.0, 0.1, ("t1",), "unreviewed"),
        PredictionRecord("q1", "q1::distractors_added", "distractors_added", "embedding", ("t1", "d1"), 1.0, 0.1, ("t1",), "unreviewed"),
    ]
    same = audit_methods_saw_identical_inputs(recs, manifests)
    assert same["identical_query_scenario_catalog_sets"] is True
    assert same["returned_ids_check"]["passed"] is True
    rows = {r["method"]: r for r in distractor_selection_breakdown(recs, manifests)}
    assert rows["bm25"]["top1_added_distractor"] == 1
    assert rows["embedding"]["top1_label_match"] == 1

    review = distractor_top1_review_rows(
        recs, manifests, {"q1": req("q1", ["t1"])}, {"t1": tool("t1"), "d1": tool("d1")}, {"q1": "test"}
    )
    assert len(review) == 1
    assert review[0]["distractor_tool_id"] == "d1" and review[0]["methods_with_this_top1"] == "bm25"
    # Added tools are not assumed irrelevant: the judgment is left to a human.
    assert review[0]["judgment_distractor_satisfies_request"] == "" and review[0]["human_reviewed"] == ""


# ---------------------------------------------------------------- thresholds


def test_count_row_reports_undefined_risk_explicitly():
    row = count_row([rec("q1", 0.1, 0.1, True)], AbstentionPolicy(SCORE_THRESHOLD, 0.5))
    assert row["n_accepted"] == 0
    assert row["selective_risk"] is None
    assert row["selective_risk_status"].startswith("UNDEFINED")
    assert row["coverage"] == 0.0 and row["coverage_ci95_high"] > 0


def test_selection_trace_reproduces_select_threshold():
    val = [rec("a", 0.9, 0.5, True), rec("b", 0.8, 0.4, True), rec("c", 0.5, 0.1, False), rec("d", 0.3, 0.0, False)]
    trace = selection_trace(val, SCORE_THRESHOLD, max_risk=0.1)
    best = max((t for t in trace if t["meets_target"]), key=lambda t: (t["coverage"], -t["selective_risk"], t["threshold"]))
    assert best["threshold"] == select_threshold(val, SCORE_THRESHOLD, max_risk=0.1).threshold == 0.8


def test_explain_threshold_detects_nonzero_val_but_zero_test_coverage():
    val = [rec("a", 10.0, 1.0, True), rec("b", 2.0, 0.5, False), rec("c", 1.0, 0.0, False)]
    test = [rec("x", 3.0, 0.5, True), rec("y", 1.5, 0.0, False)]
    t = select_threshold(val, SCORE_THRESHOLD, max_risk=0.1).threshold
    exp = explain_threshold(val, test, SCORE_THRESHOLD, t, 0.1)
    assert exp["reselected_threshold_matches_frozen"]
    assert exp["selected_val_was_zero_coverage"] is False
    assert exp["selected_val_counts"]["n_accepted"] == 1
    assert exp["test_rejected_everything"] is True
    assert exp["fallback_used"] is False
    assert exp["n_zero_margin_top1_ties_val"] == 1


def test_diagnostics_table_has_mixed_rows_and_counts():
    recs = {"test": [rec("a", 1.0, 0.1, True), rec("a", 1.0, 0.1, False, scenario="known_removed")]}
    rows = diagnostics_table(recs, {"bm25": {ALWAYS_TOP1: AbstentionPolicy(ALWAYS_TOP1)}}, 0.1, "global")
    mixed = [r for r in rows if r["scenario"] == ALL_SCENARIOS][0]
    assert (mixed["n_queries"], mixed["n_correct_accepted"], mixed["n_incorrect_accepted"]) == (2, 1, 1)


def test_paired_accuracy_difference_counts_discordant_pairs():
    a = [rec("q1", 1, 1, True), rec("q2", 1, 1, True), rec("q3", 1, 1, False)]
    b = [rec("q1", 1, 1, True), rec("q2", 1, 1, False), rec("q3", 1, 1, False)]
    d = paired_accuracy_difference(a, b, n_resamples=200)
    assert d["n_paired_queries"] == 3
    assert (d["a_only_correct"], d["b_only_correct"]) == (1, 0)
    assert math.isclose(d["diff"], 1 / 3)


# ---------------------------------------------------------------- leakage


def test_leakage_report_detects_cross_split_near_duplicates_and_shared_tools():
    requests = [
        req("q1", ["fam_1"], text="convert 100 usd to eur please"),
        req("q2", ["fam_1"], text="convert 100 usd to eur please now"),
        req("q3", ["fam_2"], text="weather in paris"),
    ]
    split_of = {"q1": "dev", "q2": "test", "q3": "val"}
    rep = leakage_report(requests, split_of, {"fam_1": tool("fam_1"), "fam_2": tool("fam_2")}, near_dup_jaccard=0.8)
    assert rep["exact_variant_groups"]["n_groups_spanning_multiple_splits"] == 0
    assert rep["near_duplicate_cross_split_pairs"]["n_pairs_by_split_pair"] == {"dev-test": 1}
    assert rep["annotated_tool_overlap"]["test_vs_dev_val"]["n_with_identical_label_set_in_earlier_splits"] == 1


# ---------------------------------------------------------------- labeling docs


def test_labeling_doc_is_blind_and_deterministic(tmp_path):
    import csv as _csv

    rdir = tmp_path / "review"
    rdir.mkdir()
    with open(rdir / "bounded_catalog_review_items.csv", "w", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=["item_id", "query_text", "n_tools_in_catalog"])
        w.writeheader()
        w.writerow({"item_id": "BC001", "query_text": "do x", "n_tools_in_catalog": 2})
    with open(rdir / "bounded_catalog_review_tools.csv", "w", newline="") as f:
        w = _csv.DictWriter(
            f, fieldnames=["item_id", "slot", "tool_id", "tool_name", "tool_description", "tool_parameters"]
        )
        w.writeheader()
        w.writerow({"item_id": "BC001", "slot": 1, "tool_id": "p_1", "tool_name": "n", "tool_description": "d", "tool_parameters": "{}"})
        w.writerow({"item_id": "BC001", "slot": 2, "tool_id": "p_2", "tool_name": "n", "tool_description": "d", "tool_parameters": "{}"})

    from tool_routing.audit.labeling_doc import load_items_and_catalogs, render_labeling_doc

    items, cats = load_items_and_catalogs(rdir)
    tmap = {t: tool(t) for t in ("p_1", "p_2")}
    doc1 = render_labeling_doc(items, tmap, seed=5)
    doc2 = render_labeling_doc(items, tmap, seed=5)
    assert doc1 == doc2
    assert "p_1" in doc1 and "p_2" in doc1  # IDs preserved
    for forbidden in ("annotated", "known_removed", "scenario", "top-1 score", "condition"):
        assert forbidden not in doc1
    # Deterministic re-shuffle: tool order differs from CSV slot order is
    # allowed but not required; what must hold is that the KEY file is
    # never opened (it doesn't even exist here) and fields are blank.
    assert "_(blank)_" in doc1


def test_validate_responses_flags_incomplete_and_inconsistent(tmp_path):
    import csv as _csv

    from tool_routing.audit.labeling_doc import (
        LabelingItem,
        RESPONSE_FIELDS,
        validate_responses,
    )

    items = [LabelingItem("BC001", "q", ("t1", "t2", "t3")), LabelingItem("BC002", "q", ("t1",))]
    p = tmp_path / "resp.csv"
    with open(p, "w", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=["item_id", *RESPONSE_FIELDS])
        w.writeheader()
        # Complete + consistent: two individually-sufficient ALTERNATIVES
        # is valid -- a single-tool request can have several valid tools.
        w.writerow({"item_id": "BC001", "individually_satisfying_tool_ids": "t1;t2",
                    "required_tool_combinations": "none", "answerability": "answerable",
                    "explanation": "t1 and t2 each do the whole job",
                    "reviewer_id": "x", "human_reviewed": "yes"})
        # Broken: unknown ID, 'answerable' contradicts itself via combo on
        # single-member group, no_suitable contradicts satisfying IDs,
        # not reviewed, no explanation.
        w.writerow({"item_id": "BC002", "individually_satisfying_tool_ids": "t9",
                    "required_tool_combinations": "t1", "answerability": "no_suitable_tool",
                    "explanation": "", "reviewer_id": "", "human_reviewed": ""})
    rep = validate_responses(p, items)
    assert rep["n_complete_and_consistent"] == 1
    joined = " ".join(rep["issues"])
    for frag in ("BC002", "not in this item's catalog", "malformed",
                 "contradicts non-empty", "human_reviewed != yes", "explanation empty"):
        assert frag in joined, frag


def test_validate_responses_combination_is_valid_multi_tool(tmp_path):
    import csv as _csv

    from tool_routing.audit.labeling_doc import (
        LabelingItem, RESPONSE_FIELDS, validate_responses,
    )

    items = [LabelingItem("BC003", "q", ("t1", "t2", "t3"))]
    p = tmp_path / "resp.csv"
    with open(p, "w", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=["item_id", *RESPONSE_FIELDS])
        w.writeheader()
        # Joint-work answer: no single tool, but t1+t2 together suffice.
        w.writerow({"item_id": "BC003", "individually_satisfying_tool_ids": "none",
                    "required_tool_combinations": "t1+t2", "answerability": "answerable",
                    "explanation": "need t1 to fetch and t2 to format",
                    "reviewer_id": "x", "human_reviewed": "yes"})
    rep = validate_responses(p, items)
    assert rep["n_complete_and_consistent"] == 1 and not rep["issues"]


def test_diagnostics_table_mixed_rows_have_query_cluster_ci():
    recs = {"test": [
        rec("a", 1.0, 0.1, True, "original"), rec("a", 1.0, 0.1, False, "known_removed"),
        rec("a", 1.0, 0.1, False, "distractors_added"),
        rec("b", 1.0, 0.1, False, "original"), rec("b", 1.0, 0.1, False, "known_removed"),
        rec("b", 1.0, 0.1, True, "distractors_added"),
    ]}
    rows = diagnostics_table(
        recs, {"bm25": {ALWAYS_TOP1: AbstentionPolicy(ALWAYS_TOP1)}}, 0.1, "global",
        cluster_bootstrap_resamples=100,
    )
    mixed = [r for r in rows if r["scenario"] == ALL_SCENARIOS][0]
    assert (mixed["n_queries"], mixed["n_correct_accepted"], mixed["n_incorrect_accepted"]) == (6, 2, 4)
    # Decision-level risk stays row-level: 4/6.
    assert abs(mixed["selective_risk"] - 4 / 6) < 1e-9
    assert mixed["selective_risk_ci95_method"] == "query_cluster_bootstrap_1000"
    assert mixed["selective_risk_ci95_rw_low"] is not None  # row-level Wilson kept, labeled
    # Separate query-level metric: both queries have >=1 accepted
    # incorrect decision -> rate 2/2.
    assert mixed["qlev_n_queries_with_accepted"] == 2
    assert mixed["qlev_n_queries_with_incorrect"] == 2
    assert mixed["qlev_rate"] == 1.0
    single = [r for r in rows if r["scenario"] == "original"][0]
    assert single["selective_risk_ci95_method"] == "wilson_independent_rows"
    assert "qlev_rate" not in single  # only mixed rows get the extra metric


# ---------------------------------------------------------------- embedding cache keys


def test_revision_immutability_check():
    assert is_immutable_revision("1110a243fdf4706b3f48f1d95db1a4f5529b4d41")
    assert not is_immutable_revision("main")
    assert not is_immutable_revision("offline-unknown")
    assert not is_immutable_revision("1110a243fdf4")
    assert not is_immutable_revision(None)


def test_embedding_cache_key_changes_with_settings_and_tool_content():
    base = {"model_name": "m", "model_revision": "a" * 40, "doc_prefix": "", "normalize_embeddings": True,
            "max_seq_length": 256, "sentence_transformers_version": "3.3.1"}
    fp = embedding_settings_fingerprint(base)
    t = tool("x_1", "does a")
    key = _tool_content_key(t, "", fp)
    assert key == _tool_content_key(tool("x_1", "does a"), "", embedding_settings_fingerprint(dict(base)))
    for change in ({"model_revision": "b" * 40}, {"max_seq_length": 128}, {"model_name": "m2"},
                   {"sentence_transformers_version": "3.4.0"}):
        assert _tool_content_key(t, "", embedding_settings_fingerprint({**base, **change})) != key
    assert _tool_content_key(tool("x_1", "does b"), "", fp) != key
    assert _tool_content_key(t, "passage: ", fp) != key
