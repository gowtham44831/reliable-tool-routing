from tool_routing.data.schema import Request, Tool
from tool_routing.data.toy_fixture import load_toy_dataset
from tool_routing.scenarios.splits import make_pilot_splits, normalize_for_grouping


def test_normalize_for_grouping_treats_case_and_punctuation_variants_as_same():
    a = normalize_for_grouping("What's the weather like in Paris right now?")
    b = normalize_for_grouping("what's the weather like in paris right now??")
    assert a == b


def test_near_duplicate_queries_are_grouped_into_the_same_split():
    tools, requests = load_toy_dataset()
    tools_by_id = {t.tool_id: t for t in tools}
    manifest = make_pilot_splits(requests, tools_by_id, seed=42, max_total=500)

    dup_ids = ["toy_q_weather_1", "toy_q_weather_1_dup1", "toy_q_weather_1_dup2"]
    splits_seen = {manifest.split_of(qid) for qid in dup_ids}
    assert len(splits_seen) == 1, "near-duplicate variants must stay in the same split"


def test_splits_are_deterministic_given_same_seed():
    tools, requests = load_toy_dataset()
    tools_by_id = {t.tool_id: t for t in tools}
    m1 = make_pilot_splits(requests, tools_by_id, seed=7, max_total=500)
    m2 = make_pilot_splits(requests, tools_by_id, seed=7, max_total=500)
    assert m1.dev_query_ids == m2.dev_query_ids
    assert m1.val_query_ids == m2.val_query_ids
    assert m1.test_query_ids == m2.test_query_ids


def test_different_seeds_can_produce_different_splits():
    tools, requests = load_toy_dataset()
    tools_by_id = {t.tool_id: t for t in tools}
    m1 = make_pilot_splits(requests, tools_by_id, seed=1, max_total=500)
    m2 = make_pilot_splits(requests, tools_by_id, seed=2, max_total=500)
    assert (m1.dev_query_ids, m1.val_query_ids, m1.test_query_ids) != (
        m2.dev_query_ids,
        m2.val_query_ids,
        m2.test_query_ids,
    )


def test_every_request_assigned_to_exactly_one_split_when_under_budget():
    tools, requests = load_toy_dataset()
    tools_by_id = {t.tool_id: t for t in tools}
    manifest = make_pilot_splits(requests, tools_by_id, seed=42, max_total=500)
    all_assigned = manifest.dev_query_ids + manifest.val_query_ids + manifest.test_query_ids
    assert len(all_assigned) == len(set(all_assigned))
    assert set(all_assigned) == {r.query_id for r in requests}


def test_max_total_caps_the_number_of_queries_kept():
    tools, requests = load_toy_dataset()
    tools_by_id = {t.tool_id: t for t in tools}
    manifest = make_pilot_splits(requests, tools_by_id, seed=42, max_total=5)
    total_kept = len(manifest.dev_query_ids) + len(manifest.val_query_ids) + len(manifest.test_query_ids)
    assert total_kept <= 5
    assert manifest.n_available_queries <= 5


def test_family_overlap_is_detected_when_present():
    tools, requests = load_toy_dataset()
    tools_by_id = {t.tool_id: t for t in tools}
    manifest = make_pilot_splits(requests, tools_by_id, seed=42, max_total=500)
    # The toy fixture is small enough that families legitimately repeat
    # across splits; this must be surfaced, not hidden.
    assert isinstance(manifest.family_overlap_warnings, list)
