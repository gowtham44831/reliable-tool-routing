from tool_routing.data.schema import Request, Tool
from tool_routing.data.toy_fixture import load_toy_dataset
from tool_routing.data.validate import validate_dataset, validate_requests, validate_tools


def make_tool(tool_id="t1", name="n", description="d"):
    return Tool(tool_id=tool_id, name=name, description=description, source_dataset="x")


def make_request(query_id="q1", text="hello", valid=("t1",)):
    return Request(query_id=query_id, query_text=text, known_valid_tool_ids=valid, source_dataset="x")


def test_toy_fixture_is_clean():
    tools, requests = load_toy_dataset()
    report = validate_dataset(tools, requests)
    assert report.is_clean, report.summary()
    assert report.n_tools == len(tools)
    assert report.n_requests == len(requests)


def test_duplicate_tool_ids_detected():
    tools = [make_tool("t1"), make_tool("t1")]
    dup, missing = validate_tools(tools)
    assert dup == ["t1"]
    assert missing == []


def test_tool_missing_fields_detected():
    tools = [make_tool("t1", name="", description="d"), make_tool("t2", name="n", description="  ")]
    dup, missing = validate_tools(tools)
    assert dup == []
    assert missing == ["t1", "t2"]


def test_dangling_tool_reference_detected():
    requests = [make_request("q1", valid=("missing_tool",))]
    report = validate_requests(requests, valid_tool_ids={"t1"})
    assert report.dangling_tool_refs == {"q1": ["missing_tool"]}
    assert not report.is_clean


def test_duplicate_query_ids_detected():
    requests = [make_request("q1"), make_request("q1")]
    report = validate_requests(requests, valid_tool_ids={"t1"})
    assert report.duplicate_query_ids == ["q1"]


def test_conflicting_labels_detected():
    requests = [
        make_request("q1", valid=("t1",)),
        make_request("q1", valid=("t2",)),
    ]
    report = validate_requests(requests, valid_tool_ids={"t1", "t2"})
    assert "q1" in report.conflicting_labels


def test_requests_without_any_valid_tool_recorded_not_dropped():
    requests = [make_request("q1", valid=())]
    report = validate_requests(requests, valid_tool_ids={"t1"})
    assert report.requests_without_any_valid_tool == ["q1"]
    # Missing labels must not be silently treated as a hard validation error.
    assert report.dangling_tool_refs == {}
