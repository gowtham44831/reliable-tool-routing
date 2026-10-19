from tool_routing.evaluation.records import PredictionRecord
from tool_routing.evaluation.thresholds import (
    ALWAYS_TOP1,
    MARGIN_THRESHOLD,
    SCORE_THRESHOLD,
    AbstentionPolicy,
    select_threshold,
)


def rec(qid, top1_score, margin, correct=True, answerable="answerable"):
    valid = ("t1",) if correct else ("other",)
    return PredictionRecord(
        query_id=qid,
        catalog_id=f"{qid}::original",
        scenario="original",
        method="bm25",
        top_k_tool_ids=("t1", "t2"),
        top1_score=top1_score,
        margin=margin,
        known_valid_tool_ids=valid,
        answerability_review_status=answerable,
    )


def test_always_top1_never_abstains():
    policy = AbstentionPolicy(ALWAYS_TOP1)
    r = rec("q1", top1_score=0.0, margin=0.0)
    assert policy.should_abstain(r) is False


def test_score_threshold_abstains_below_threshold():
    policy = AbstentionPolicy(SCORE_THRESHOLD, threshold=0.5)
    assert policy.should_abstain(rec("q1", top1_score=0.3, margin=0.1)) is True
    assert policy.should_abstain(rec("q1", top1_score=0.7, margin=0.1)) is False


def test_margin_threshold_does_not_abstain_when_margin_undefined():
    policy = AbstentionPolicy(MARGIN_THRESHOLD, threshold=0.5)
    r = PredictionRecord(
        query_id="q1",
        catalog_id="q1::original",
        scenario="original",
        method="bm25",
        top_k_tool_ids=("t1",),
        top1_score=1.0,
        margin=None,
        known_valid_tool_ids=("t1",),
        answerability_review_status="answerable",
    )
    assert policy.should_abstain(r) is False


def test_threshold_selection_uses_only_validation_records():
    val_records = [
        rec("v1", top1_score=0.9, margin=0.5, correct=True),
        rec("v2", top1_score=0.8, margin=0.4, correct=True),
        rec("v3", top1_score=0.2, margin=0.1, correct=False),
    ]
    policy = select_threshold(val_records, SCORE_THRESHOLD, max_risk=0.0)
    # Only threshold achieving zero risk on val keeps the two correct,
    # high-scoring predictions and excludes the incorrect low-scoring one.
    assert policy.threshold <= 0.8
    assert policy.threshold > 0.2

    # Changing a disjoint set of "test" records must not affect the policy
    # already selected from val_records (selection is a pure function of
    # its input, not of any later test-time data).
    test_records = [rec("t1", top1_score=0.99, margin=0.9, correct=False)]
    policy_again = select_threshold(val_records, SCORE_THRESHOLD, max_risk=0.0)
    assert policy_again.threshold == policy.threshold
    assert test_records  # test_records never passed into select_threshold


def test_threshold_selection_falls_back_when_no_threshold_meets_target():
    # The only candidate is always incorrect, so no threshold can ever
    # achieve the requested max_risk=0.0. select_threshold must fall back
    # explicitly to the lowest-risk option rather than silently reporting
    # a threshold that achieves zero risk from zero accepted queries.
    val_records = [rec("v1", top1_score=0.1, margin=0.05, correct=False)]
    policy = select_threshold(val_records, SCORE_THRESHOLD, max_risk=0.0)
    assert policy.threshold == float("-inf")


def test_threshold_selection_on_empty_validation_set_abstains_on_everything():
    policy = select_threshold([], SCORE_THRESHOLD, max_risk=0.0)
    assert policy.threshold == float("inf")
    r = rec("v1", top1_score=0.99, margin=0.5, correct=True)
    assert policy.should_abstain(r) is True
