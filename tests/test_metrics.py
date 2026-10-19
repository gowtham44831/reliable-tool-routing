from tool_routing.evaluation.metrics import compute_metrics, query_grouped_bootstrap_ci
from tool_routing.evaluation.records import PredictionRecord
from tool_routing.evaluation.thresholds import ALWAYS_TOP1, SCORE_THRESHOLD, AbstentionPolicy


def rec(qid, top_k, score, margin, valid, status="answerable"):
    return PredictionRecord(
        query_id=qid,
        catalog_id=f"{qid}::original",
        scenario="original",
        method="bm25",
        top_k_tool_ids=top_k,
        top1_score=score,
        margin=margin,
        known_valid_tool_ids=valid,
        answerability_review_status=status,
    )


def test_hand_computed_accuracy_and_recall():
    # 4 answerable queries: 3 correct top-1, 1 incorrect. top-1 acc = 0.75.
    records = [
        rec("q1", ("t1", "t2"), 1.0, 0.5, ("t1",)),
        rec("q2", ("t1", "t2"), 1.0, 0.5, ("t1",)),
        rec("q3", ("t1", "t2"), 1.0, 0.5, ("t1",)),
        rec("q4", ("t2", "t1"), 1.0, 0.5, ("t1",)),  # top1 wrong, but recall@2 true
    ]
    policy = AbstentionPolicy(ALWAYS_TOP1)
    m = compute_metrics(records, policy)
    assert m.coverage == 1.0
    assert m.top1_accuracy == 0.75
    assert m.recall_at_k[1] == 0.75
    assert m.recall_at_k[3] == 1.0  # top_k only has 2 entries, but all contain t1
    assert m.selective_risk == 0.25


def test_zero_coverage_is_explicit_not_zero_risk():
    records = [rec("q1", ("t1",), 0.1, 0.0, ("t1",))]
    # Threshold above every score => nothing accepted.
    policy = AbstentionPolicy(SCORE_THRESHOLD, threshold=10.0)
    m = compute_metrics(records, policy)
    assert m.coverage == 0.0
    assert m.n_accepted == 0
    assert m.selective_risk is None  # NOT 0.0
    assert m.top1_accuracy is None


def test_empty_catalog_yields_no_prediction_and_counts_as_abstained_by_default_policy():
    records = [rec("q1", (), None, None, ("t1",))]
    policy = AbstentionPolicy(ALWAYS_TOP1)
    m = compute_metrics(records, policy)
    assert m.n_accepted == 0
    assert m.coverage == 0.0
    assert m.selective_risk is None


def test_empty_records_list():
    m = compute_metrics([], AbstentionPolicy(ALWAYS_TOP1))
    assert m.n_total == 0
    assert m.coverage == 0.0
    assert m.selective_risk is None


def test_false_action_rate_only_uses_audited_unanswerable():
    records = [
        rec("q1", ("t1",), 0.9, 0.5, (), status="unanswerable"),  # accepted anyway -> false action
        rec("q2", ("t1",), 0.1, 0.0, (), status="unanswerable"),
        rec("q3", ("t1",), 0.9, 0.5, ("t1",), status="answerable"),
    ]
    policy = AbstentionPolicy(SCORE_THRESHOLD, threshold=0.5)
    m = compute_metrics(records, policy)
    assert m.n_audited_unanswerable == 2
    assert m.false_action_rate == 0.5  # 1 of 2 unanswerable queries got an action


def test_bootstrap_ci_groups_by_query_id():
    records = [
        rec("q1", ("t1",), 0.9, 0.5, ("t1",)),
        rec("q1", ("t2",), 0.9, 0.5, ("t1",)),  # same base query, different scenario
        rec("q2", ("t1",), 0.9, 0.5, ("other",)),
    ]
    policy = AbstentionPolicy(ALWAYS_TOP1)
    ci = query_grouped_bootstrap_ci(
        records,
        policy,
        lambda recs, pol: compute_metrics(recs, pol).selective_risk,
        n_resamples=50,
        seed=1,
    )
    assert ci["n_resamples_used"] > 0
    assert ci["ci_low"] is not None and ci["ci_high"] is not None
    assert ci["ci_low"] <= ci["point_estimate"] <= ci["ci_high"]
