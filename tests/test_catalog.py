from tool_routing.data.schema import Request, Tool
from tool_routing.scenarios.catalog import (
    DISTRACTORS_ADDED,
    KNOWN_REMOVED,
    ORIGINAL,
    DistractorPicker,
    build_catalog_scenarios,
)


def make_tools(ids):
    return [Tool(tool_id=i, name=i, description=f"does {i} things", source_dataset="x") for i in ids]


def test_known_removed_removes_all_annotated_valid_tools():
    request = Request(
        query_id="q1",
        query_text="do the thing",
        known_valid_tool_ids=("t1", "t2"),
        source_dataset="x",
    )
    scenarios = build_catalog_scenarios(request, ["t1", "t2", "t3", "t4"], distractor_picker=None)
    removed = scenarios[KNOWN_REMOVED]
    assert "t1" not in removed.tool_ids
    assert "t2" not in removed.tool_ids
    assert set(removed.tool_ids) == {"t3", "t4"}
    assert set(removed.removed_known_valid_ids) == {"t1", "t2"}


def test_known_removed_handles_valid_tool_not_in_pool():
    # A known-valid tool id that isn't even in the original pool shouldn't
    # break anything or appear as "removed".
    request = Request(query_id="q1", query_text="x", known_valid_tool_ids=("absent",), source_dataset="x")
    scenarios = build_catalog_scenarios(request, ["t1", "t2"], distractor_picker=None)
    assert set(scenarios[KNOWN_REMOVED].tool_ids) == {"t1", "t2"}
    assert scenarios[KNOWN_REMOVED].removed_known_valid_ids == ()


def test_original_catalog_is_deduplicated_and_sorted():
    request = Request(query_id="q1", query_text="x", known_valid_tool_ids=(), source_dataset="x")
    scenarios = build_catalog_scenarios(request, ["t2", "t1", "t1"], distractor_picker=None)
    assert scenarios[ORIGINAL].tool_ids == ("t1", "t2")


def test_distractors_added_are_genuine_additions_without_duplicates():
    held_out = make_tools(["d1", "d2", "d3"])
    picker = DistractorPicker(held_out)
    request = Request(
        query_id="q1",
        query_text="does d1 things",
        known_valid_tool_ids=("t1",),
        source_dataset="x",
    )
    scenarios = build_catalog_scenarios(request, ["t1", "t2"], picker, n_distractors=2)
    added = scenarios[DISTRACTORS_ADDED]

    # No duplicate tool ids in the resulting catalog.
    assert len(added.tool_ids) == len(set(added.tool_ids))
    # Original tools are preserved.
    assert "t1" in added.tool_ids and "t2" in added.tool_ids
    # Distractors are genuinely new (not already in the original pool).
    assert set(added.added_distractor_ids).isdisjoint({"t1", "t2"})
    assert len(added.added_distractor_ids) <= 2
    assert set(added.added_distractor_ids).issubset({"d1", "d2", "d3"})


def test_distractor_picker_never_returns_excluded_ids():
    held_out = make_tools(["d1", "d2"])
    picker = DistractorPicker(held_out)
    picked = picker.pick("some query about d1", n=5, exclude_ids={"d1"})
    assert "d1" not in picked
    assert set(picked).issubset({"d2"})


def test_empty_original_pool_yields_empty_catalogs():
    request = Request(query_id="q1", query_text="x", known_valid_tool_ids=("t1",), source_dataset="x")
    scenarios = build_catalog_scenarios(request, [], distractor_picker=None)
    assert scenarios[ORIGINAL].tool_ids == ()
    assert scenarios[KNOWN_REMOVED].tool_ids == ()
