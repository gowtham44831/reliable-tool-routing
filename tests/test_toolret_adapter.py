import json

import pandas as pd
import pytest

pytest.importorskip("pyarrow")

from tool_routing.data.toolret_adapter import (
    _parse_tool_doc,
    load_toolret_requests,
    load_toolret_tools,
)


def test_parse_tool_doc_flat_schema():
    doc = json.dumps({"name": "get_weather", "description": "Gets weather.", "parameters": {"city": {"type": "str"}}})
    name, description, params = _parse_tool_doc("x_tool_1", doc)
    assert name == "get_weather"
    assert description == "Gets weather."
    assert params == {"city": {"type": "str"}}


def test_parse_tool_doc_api_call_schema_falls_back_gracefully():
    doc = json.dumps(
        {
            "domain": "Image classification",
            "framework": "TensorFlow Hub",
            "functionality": "Classify images",
            "api_call": "hub.load('https://tfhub.dev/x')",
            "api_arguments": {"model_id": "str"},
        }
    )
    name, description, params = _parse_tool_doc("gorilla_tensor_tool_0", doc)
    assert description == "Classify images"
    assert params == {"model_id": "str"}
    assert name  # some non-empty best-effort name


def test_parse_tool_doc_handles_malformed_json():
    name, description, params = _parse_tool_doc("x_tool_1", "not json")
    assert name == "x_tool_1"
    assert params == {}


def test_relevance_label_mapping(tmp_path):
    tools_df = pd.DataFrame(
        [
            {"id": "src_tool_1", "documentation": json.dumps({"name": "a", "description": "A tool"})},
            {"id": "src_tool_2", "documentation": json.dumps({"name": "b", "description": "B tool"})},
        ]
    )
    (tmp_path / "tools").mkdir()
    tools_df.to_parquet(tmp_path / "tools" / "web.parquet")

    labels = json.dumps(
        [
            {"id": "src_tool_1", "doc": {}, "relevance": 1},
            {"id": "src_tool_2", "doc": {}, "relevance": 0},
        ]
    )
    queries_df = pd.DataFrame(
        [{"id": "q1", "query": "do a thing", "instruction": "...", "labels": labels, "category": "web"}]
    )
    (tmp_path / "queries").mkdir()
    queries_df.to_parquet(tmp_path / "queries" / "src.parquet")

    tools = load_toolret_tools(tmp_path)
    requests, warnings = load_toolret_requests(tmp_path, ["src"])

    assert warnings == []
    assert len(requests) == 1
    req = requests[0]
    # relevance=1 included, relevance=0 excluded.
    assert req.known_valid_tool_ids == ("toolret_src_tool_1",)
    assert "toolret_src_tool_1" in tools
    assert "toolret_src_tool_2" in tools


def test_missing_queries_file_reports_warning_not_crash(tmp_path):
    (tmp_path / "queries").mkdir()
    (tmp_path / "tools").mkdir()
    requests, warnings = load_toolret_requests(tmp_path, ["does_not_exist"])
    assert requests == []
    assert len(warnings) == 1
